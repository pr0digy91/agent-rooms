"""Core simulation: characters, rooms, and a turn-by-turn conversation loop on AG2."""

from __future__ import annotations

import asyncio
import json
import os
import random
import sqlite3
import re
import threading
from contextlib import closing
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ag2 import Agent
from ag2.config import OpenAIConfig

from voice import MAX_SPEED, MIN_SPEED, clean_delivery, speakable

XAI_BASE_URL = "https://api.x.ai/v1"
DB_FILE = Path(__file__).parent / "agent_rooms.db"
STATE_FILE = Path(__file__).parent / "state.json"  # legacy, imported once
CONVO_DIR = Path(__file__).parent / "conversations"  # legacy, imported once

RECENT_WINDOW = 12  # newest messages always kept verbatim
SUMMARIZE_AFTER = 30  # unsummarized messages before older ones get condensed
MIN_NEW_FOR_MEMORY = 2  # new messages a character must have missed to refresh memory


@dataclass
class Character:
    name: str
    persona: str  # who they are
    behavior: str  # how they act / speak
    voice: str = "eve"  # xAI TTS voice used when speaking aloud


@dataclass
class Room:
    name: str
    description: str  # the environment
    rules: str = ""  # optional house rules / world rules


@dataclass
class Message:
    speaker: str  # who spoke; for world events, the kind of thing (e.g. "Artifact")
    text: str
    kind: str = "chat"  # "chat" | "manifest" (something appeared) | "banish" (something was removed)


MANIFEST_KINDS = {
    "Idea": "a concept, memory or piece of knowledge everyone suddenly holds in mind",
    "Artifact": "an object of power or mystery that suddenly appears",
    "Physical object": "a physical thing that is suddenly there",
    "Entity": "a being, creature or presence that is suddenly here",
    "Phenomenon": "an event or force that suddenly takes hold of the environment",
}


@dataclass
class Manifestation:
    kind: str
    name: str
    description: str = ""
    active: bool = True
    conviction: int = 50  # 0-100: how firmly everyone believes in it and what it claims


@dataclass
class Conversation:
    room: str = ""
    cast: list[str] = field(default_factory=list)
    history: list[Message] = field(default_factory=list)
    summary: str = ""  # rolling summary of history[:summarized]
    summarized: int = 0
    memories: dict[str, str] = field(default_factory=dict)  # private notes per character
    seen: dict[str, int] = field(default_factory=dict)  # history index each character has processed
    manifestations: list[Manifestation] = field(default_factory=list)  # things the user brought into the scene


@dataclass
class State:
    characters: list[Character] = field(default_factory=list)
    rooms: list[Room] = field(default_factory=list)
    player: Character = field(default_factory=lambda: Character("You", "", ""))  # the human


DEFAULT_CHARACTERS = [
    Character(
        "Captain Mara",
        "A weathered starship captain who has seen too many wars.",
        "Blunt, dry humor, protective of her crew. Speaks in short sentences.",
        "ara",
    ),
    Character(
        "Pip",
        "A cheerful, curious ship's engineer, barely out of the academy.",
        "Enthusiastic, rambles about gadgets, asks lots of questions, a little naive.",
        "leo",
    ),
    Character(
        "Dr. Voss",
        "A skeptical scientist who distrusts authority.",
        "Precise, sarcastic, loves to challenge assumptions with data.",
        "rex",
    ),
]
DEFAULT_ROOMS = [
    Room(
        "Starship Mess Hall",
        "The cramped mess hall of the starship Wanderer, deep in uncharted space. "
        "The lights flicker; something strange is showing up on sensors.",
        "Stay in character. Nobody can leave the ship.",
    ),
    Room(
        "Rainy Cafe",
        "A cozy cafe at night while it pours outside. Warm lights, the smell of coffee.",
        "",
    ),
]


# ---------------------------------------------------------------- storage (SQLite)
SCHEMA = """
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, persona TEXT, behavior TEXT,
    voice TEXT DEFAULT 'eve');
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, description TEXT, rules TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS conversations (
    name TEXT PRIMARY KEY, room TEXT, cast_json TEXT, summary TEXT, summarized INTEGER,
    memories_json TEXT, seen_json TEXT, manifestations_json TEXT DEFAULT '[]',
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS messages (
    conversation TEXT NOT NULL REFERENCES conversations(name) ON DELETE CASCADE,
    idx INTEGER NOT NULL, speaker TEXT, text TEXT, kind TEXT DEFAULT 'chat', PRIMARY KEY (conversation, idx));
CREATE TABLE IF NOT EXISTS clips (
    conversation TEXT NOT NULL REFERENCES conversations(name) ON DELETE CASCADE,
    idx INTEGER NOT NULL, mp3 BLOB NOT NULL, PRIMARY KEY (conversation, idx));
"""


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_FILE)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    if "voice" not in {r[1] for r in con.execute("PRAGMA table_info(characters)")}:
        con.execute("ALTER TABLE characters ADD COLUMN voice TEXT DEFAULT 'eve'")  # older databases
    for table, column, ddl in (("conversations", "manifestations_json", "TEXT DEFAULT '[]'"),
                               ("messages", "kind", "TEXT DEFAULT 'chat'")):
        if column not in {r[1] for r in con.execute(f"PRAGMA table_info({table})")}:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    return con


def _is_pristine(con: sqlite3.Connection) -> bool:
    """True if the DB holds nothing but the untouched example data (nothing the user made)."""
    chars = [tuple(r) for r in con.execute("SELECT name, persona, behavior FROM characters ORDER BY id")]
    rooms = [tuple(r) for r in con.execute("SELECT name, description, rules FROM rooms ORDER BY id")]
    row = con.execute("SELECT value FROM settings WHERE key='player'").fetchone()
    player_default = not row or (lambda p: p.get("name") == "You" and not p.get("persona"))(json.loads(row[0]))
    return (
        player_default
        and chars in ([], [(c.name, c.persona, c.behavior) for c in DEFAULT_CHARACTERS])
        and rooms in ([], [(r.name, r.description, r.rules) for r in DEFAULT_ROOMS])
    )


def _import_legacy_json(con: sqlite3.Connection) -> None:
    """One-time import of state.json / conversations/*.json from the pre-SQLite version.

    Runs once, tracked by the 'legacy_imported' setting (not by whether the DB file existed).
    If the DB still holds only the example data, the legacy data replaces it; otherwise it is
    merged without overwriting anything already in the DB.
    """
    if con.execute("SELECT 1 FROM settings WHERE key='legacy_imported'").fetchone():
        return
    con.execute("INSERT INTO settings VALUES ('legacy_imported', '1')")
    if STATE_FILE.exists():
        raw = json.loads(STATE_FILE.read_text())
        if _is_pristine(con) and raw.get("characters"):
            con.execute("DELETE FROM characters")
            con.execute("DELETE FROM rooms")
            con.execute("DELETE FROM settings WHERE key='player'")
        default_voice = {c.name: c.voice for c in DEFAULT_CHARACTERS}
        con.executemany("INSERT OR IGNORE INTO characters(name, persona, behavior, voice) VALUES (?,?,?,?)",
                        [(c["name"], c["persona"], c["behavior"], c.get("voice") or default_voice.get(c["name"], "eve"))
                         for c in raw.get("characters", [])])
        con.executemany("INSERT OR IGNORE INTO rooms(name, description, rules) VALUES (?,?,?)",
                        [(r["name"], r["description"], r.get("rules", "")) for r in raw.get("rooms", [])])
        if raw.get("player"):
            con.execute("INSERT OR IGNORE INTO settings VALUES ('player', ?)", (json.dumps(raw["player"]),))
    if CONVO_DIR.exists():
        for p in CONVO_DIR.glob("*.json"):
            if not con.execute("SELECT 1 FROM conversations WHERE name = ?", (p.stem,)).fetchone():
                raw = json.loads(p.read_text())
                raw["history"] = [Message(**m) for m in raw.get("history", [])]
                _write_conversation(con, p.stem, Conversation(**raw))


def load_state() -> State:
    with closing(_db()) as con, con:
        _import_legacy_json(con)
        chars = [Character(*r) for r in con.execute("SELECT name, persona, behavior, voice FROM characters ORDER BY id")]
        rooms = [Room(*r) for r in con.execute("SELECT name, description, rules FROM rooms ORDER BY id")]
        row = con.execute("SELECT value FROM settings WHERE key='player'").fetchone()
        player = Character(**json.loads(row[0])) if row else Character("You", "", "")
        seeded = con.execute("SELECT value FROM settings WHERE key='seeded'").fetchone()
        if not seeded:  # fresh install: start with the example cast and rooms
            if not chars and not rooms:
                chars, rooms = list(DEFAULT_CHARACTERS), list(DEFAULT_ROOMS)
            con.execute("INSERT INTO settings VALUES ('seeded', '1')")
            st = State(chars, rooms, player)
            _write_state(con, st)
            return st
    return State(chars, rooms, player)


def _write_state(con: sqlite3.Connection, state: State) -> None:
    con.execute("DELETE FROM characters")
    con.execute("DELETE FROM rooms")
    con.executemany("INSERT OR REPLACE INTO characters(name, persona, behavior, voice) VALUES (?,?,?,?)",
                    [(c.name, c.persona, c.behavior, c.voice) for c in state.characters])
    con.executemany("INSERT OR REPLACE INTO rooms(name, description, rules) VALUES (?,?,?)",
                    [(r.name, r.description, r.rules) for r in state.rooms])
    con.execute("INSERT OR REPLACE INTO settings VALUES ('player', ?)", (json.dumps(asdict(state.player)),))


def get_setting(key: str, default: str = "") -> str:
    with closing(_db()) as con:
        row = con.execute("SELECT value FROM settings WHERE key = ?", (f"ui:{key}",)).fetchone()
    return row[0] if row else default


def set_setting(key: str, value: str) -> None:
    with closing(_db()) as con, con:
        con.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (f"ui:{key}", value))


def save_state(state: State) -> None:
    with closing(_db()) as con, con:
        _write_state(con, state)


def make_config(temperature: float = 0.9):
    key = os.getenv("XAI_API_KEY")
    if not key:
        raise RuntimeError("XAI_API_KEY is not set. Add it to your .env file.")
    return OpenAIConfig(
        model=os.getenv("XAI_MODEL", "grok-4.20-0309-non-reasoning"),
        api_key=key,
        base_url=XAI_BASE_URL,
        temperature=temperature,
    )


def _belief_rules(world: list[Manifestation] | None) -> str:
    """Hard, last-in-prompt rules for strongly believed manifestations; they outrank persona, notes and old doubts."""
    firm = [w for w in (world or []) if w.active and w.conviction >= 85]
    low = [w for w in (world or []) if w.active and w.conviction <= 15]
    out = ""
    if firm:
        names = ", ".join(f'"{w.name}"' for w in firm)
        out += (f"BELIEF RULE (overrides your personality, your private notes and anything you said earlier): "
                f"{names} {'is' if len(firm) == 1 else 'are'} fully established truth. You do NOT doubt, test, "
                "suspect, or call it a trick, trap, manipulation or fake, and you do not demand proof or further "
                "checks. Your earlier suspicions are resolved by it. You may still feel emotions (awe, relief, "
                "fear, anger) and react in your own voice, but you accept it and act on it.\n\n")
    if low:
        names = ", ".join(f'"{w.name}"' for w in low)
        out += (f"BELIEF RULE: you do not believe what {names} claims; you resist it, whatever others say.\n\n")
    return out


def _world_block(world: list[Manifestation] | None) -> str:
    active = [w for w in (world or []) if w.active]
    if not active:
        return ""
    items = "\n".join(
        f"- {w.kind}: {w.name}" + (f" - {w.description}" if w.description else "")
        + f" [belief {w.conviction}/100: {_belief(w.conviction)}]"
        for w in active)
    return ("Manifested into this world by an outside force. These are real, everyone present perceives "
            "them at once, and they stay until they are removed. Keep them in mind and react as your "
            f"character would, and let each item's belief level shape how readily you accept it:\n{items}\n\n")


def _belief(conviction: int) -> str:
    if conviction >= 95:
        return ("everyone accepts it without doubt: it is simply true in this world, including whatever it "
                "claims, says or shows. Earlier doubts melt away; adapt your plans and feelings to it")
    if conviction >= 70:
        return ("you are inclined to believe it and what it claims, and you act on it; only a deeply stubborn "
                "trait would hold out, and briefly")
    if conviction >= 40:
        return ("judge it by your own character: trusting characters lean towards accepting it, suspicious "
                "ones want proof")
    if conviction >= 15:
        return ("it is physically there, but you doubt what it claims, demand evidence and put your own "
                "beliefs and instruments first")
    return "you may accept that it is present, but you reject what it claims or implies and resist changing your mind"


def _system_prompt(c: Character, room: Room, others: list[str], summary: str, memory: str,
                   player: Character | None = None, world: list[Manifestation] | None = None) -> str:
    return (
        f"You are {c.name}, a character in a live roleplay simulation.\n"
        f"Who you are: {c.persona}\n"
        f"How you behave: {c.behavior}\n\n"
        f"Setting ({room.name}): {room.description}\n"
        f"{('Room rules: ' + room.rules) if room.rules else ''}\n"
        f"Others present: {', '.join(others) or 'nobody else'}.\n"
        + (f"{player.name} is a real human taking part in the scene (they type their lines in; "
           f"you never write for them). About them: {player.persona or 'unknown'}. "
           f"Their nature: {player.behavior or 'unknown'}. Treat them as a full participant "
           "and respond to them when they speak.\n" if player else "")
        + "\n"
        + _world_block(world)
        + (f"Story so far (summary): {summary}\n\n" if summary else "")
        + (f"Your private memory notes (only you know these):\n{memory}\n\n" if memory else "")
        + _belief_rules(world)
        + "Reply ONLY with what you say or do next, in 1-3 short sentences. Actions go "
        "in *asterisks*. Never speak for other characters, never narrate their "
        "reactions, and don't prefix your reply with your name. React naturally to "
        "what was just said; stay consistent with your memory; move the scene forward "
        "rather than repeating yourself."
    )


def _lines(msgs: list[Message]) -> str:
    def one(m: Message) -> str:
        if m.kind == "manifest":
            return f"[WORLD EVENT: {m.speaker} suddenly manifests] {m.text.replace(chr(10), ': ', 1)}"
        if m.kind == "banish":
            return f"[WORLD EVENT: this suddenly vanishes] {m.text.replace(chr(10), ': ', 1)}"
        return f"{m.speaker}: {m.text}"
    return "\n".join(one(m) for m in msgs)


_loop = asyncio.new_event_loop()
threading.Thread(target=_loop.run_forever, daemon=True).start()


def run_async(coro):
    """Run on one long-lived loop so pooled HTTP clients never outlive their loop."""
    return asyncio.run_coroutine_threadsafe(coro, _loop).result()


async def _ask(agent: Agent, prompt: str) -> str:
    reply = await agent.ask(prompt)
    return (reply.body or "").strip()


def _ask_sync(name: str, system: str, prompt: str, config) -> str:
    return run_async(_ask(Agent(name, system, config=config), prompt))


_TITLES = {"dr", "mr", "mrs", "ms", "mx", "sir", "lady", "lord", "captain", "prof", "professor"}


def addressed_character(msg: Message, cast: list[Character]) -> Character | None:
    """The character (other than the author) whose name appears earliest in the message."""
    best: tuple[int, Character] | None = None
    for c in cast:
        if c.name == msg.speaker:
            continue
        parts = [c.name] + [t for t in re.findall(r"\w+", c.name) if t.lower() not in _TITLES and len(t) >= 3]
        for p in parts:
            m = re.search(rf"\b{re.escape(p)}\b", msg.text, re.IGNORECASE)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), c)
    return best[1] if best else None


def pick_speaker(mode: str, cast: list[Character], history: list[Message], config,
                 prefer_addressed: bool = True) -> Character:
    last = history[-1].speaker if history else None
    if prefer_addressed and history and (target := addressed_character(history[-1], cast)):
        return target
    candidates = [c for c in cast if c.name != last] or cast
    if mode == "Round robin":
        names = [c.name for c in cast]
        spoken = [m.speaker for m in history if m.speaker in names]
        return cast[0] if not spoken else cast[(names.index(spoken[-1]) + 1) % len(cast)]
    if mode == "Random":
        return random.choice(candidates)
    # "Director": the model decides who would most naturally speak next
    answer = _ask_sync(
        "Director",
        "You direct a roleplay scene. Given the transcript, choose who should speak "
        "next so the conversation flows naturally (e.g. someone addressed, someone "
        "with a strong reaction). Answer with ONLY one name from the list.",
        f"Candidates: {', '.join(c.name for c in candidates)}\n"
        "If the last message is clearly directed at one candidate, pick that one.\n\nTranscript:\n{_lines(history[-20:])}",
        config,
    )
    for c in candidates:
        if c.name.lower() in answer.lower():
            return c
    return random.choice(candidates)


def maybe_summarize(convo: Conversation, config) -> None:
    """Condense older messages into the rolling summary, keeping RECENT_WINDOW verbatim."""
    if len(convo.history) - convo.summarized <= SUMMARIZE_AFTER:
        return
    end = len(convo.history) - RECENT_WINDOW
    chunk = convo.history[convo.summarized:end]
    convo.summary = _ask_sync(
        "Summarizer",
        "You maintain a running summary of a roleplay. Merge the previous summary "
        "and the new messages into one concise summary (max ~200 words): key events, "
        "decisions, revealed facts, and relationships. Output only the summary.",
        f"Previous summary:\n{convo.summary or '(none)'}\n\nNew messages:\n{_lines(chunk)}",
        config,
    )
    convo.summarized = end


def refresh_memory(c: Character, convo: Conversation, config) -> None:
    """The character privately jots down what they've missed since they last updated."""
    start = max(convo.seen.get(c.name, 0), convo.summarized)
    new = convo.history[start:]
    if len(new) < MIN_NEW_FOR_MEMORY:
        return
    convo.memories[c.name] = _ask_sync(
        "NoteTaker",
        f"You are a note-taking assistant. You maintain {c.name}'s private memory notes "
        f"(character: {c.persona}) for a roleplay, written in first person from {c.name}'s "
        "point of view: facts learned, feelings about others, secrets, goals, unresolved "
        "threads. Merge the old notes with the new events. Output ONLY terse bullet points "
        "(each starting with '- '), under 150 words. Do NOT roleplay, do NOT write dialogue "
        "or actions, do NOT address anyone.",
        f"Old notes:\n{convo.memories.get(c.name, '(none)')}\n\nNew events:\n{_lines(new)}",
        config,
    )
    convo.seen[c.name] = len(convo.history)


def next_turn(room: Room, cast: list[Character], convo: Conversation, mode: str, config,
              use_memory: bool = True, player: Character | None = None,
              prefer_addressed: bool = True, candidates: list[Character] | None = None) -> Message:
    """Generate exactly one new message in the room and append it to the conversation.

    `candidates` limits who may speak next (e.g. everyone who hasn't yet reacted to a manifestation).
    """
    history = convo.history
    speaker = pick_speaker(mode, candidates or cast, history, config, prefer_addressed) if history else cast[0]
    if use_memory:
        maybe_summarize(convo, config)
        refresh_memory(speaker, convo, config)
    recent = history[convo.summarized:]
    system = _system_prompt(
        speaker, room, [c.name for c in cast if c is not speaker],
        convo.summary, convo.memories.get(speaker.name, ""), player, convo.manifestations,
    )
    prompt = (
        f"Recent conversation:\n{_lines(recent)}\n\nYour turn, {speaker.name}."
        if history
        else f"The scene begins. You, {speaker.name}, speak first."
    )
    firm = [w.name for w in convo.manifestations if w.active and w.conviction >= 85]
    if firm:
        prompt += f" Remember the belief rule: {', '.join(firm)} is accepted as true; do not doubt it."
    if history and history[-1].kind == "manifest":
        prompt += (" Something was JUST manifested into the scene (the last world event). It appeared "
                   "suddenly and it is real: react to it right now, in character.")
    elif history and history[-1].kind == "banish":
        prompt += " Something just vanished from the scene (the last world event). React in character."
    text = _ask_sync(speaker.name, system, prompt, config)
    if text.startswith(f"{speaker.name}:"):
        text = text[len(speaker.name) + 1:].strip()
    msg = Message(speaker.name, text)
    history.append(msg)
    return msg


# ------------------------------------------------------------- manifestations
def manifest(convo: Conversation, kind: str, name: str, description: str = "", conviction: int = 50) -> Message:
    """Introduce something into the shared world: every character now knows about it."""
    convo.manifestations.append(Manifestation(kind, name.strip(), description.strip(), conviction=int(conviction)))
    msg = Message(kind, f"{name.strip()}\n{description.strip()}".strip(), "manifest")
    convo.history.append(msg)
    return msg


def banish(convo: Conversation, index: int) -> Message | None:
    """Remove a manifested thing from the world; everyone sees it go."""
    if not (0 <= index < len(convo.manifestations)) or not convo.manifestations[index].active:
        return None
    w = convo.manifestations[index]
    w.active = False
    msg = Message(w.kind, w.name, "banish")
    convo.history.append(msg)
    return msg


# ------------------------------------------------------------- save / load
def _write_conversation(con: sqlite3.Connection, name: str, convo: Conversation) -> None:
    con.execute("DELETE FROM conversations WHERE name = ?", (name,))  # cascades to messages
    con.execute(
        "INSERT INTO conversations(name, room, cast_json, summary, summarized, memories_json, seen_json,"
        " manifestations_json) VALUES (?,?,?,?,?,?,?,?)",
        (name, convo.room, json.dumps(convo.cast), convo.summary, convo.summarized,
         json.dumps(convo.memories), json.dumps(convo.seen),
         json.dumps([asdict(w) for w in convo.manifestations])),
    )
    con.executemany("INSERT INTO messages(conversation, idx, speaker, text, kind) VALUES (?,?,?,?,?)",
                    [(name, i, m.speaker, m.text, m.kind) for i, m in enumerate(convo.history)])


def save_conversation(name: str, convo: Conversation, clips: dict[int, bytes] | None = None) -> None:
    """Save a conversation; `clips` (message index -> mp3) are stored with it so replays survive reloads."""
    name = name.strip() or "untitled"
    with closing(_db()) as con, con:
        _write_conversation(con, name, convo)
        con.execute("DELETE FROM clips WHERE conversation = ?", (name,))
        con.executemany("INSERT INTO clips(conversation, idx, mp3) VALUES (?,?,?)",
                        [(name, i, b) for i, b in (clips or {}).items() if i < len(convo.history)])


def load_clips(name: str) -> dict[int, bytes]:
    with closing(_db()) as con:
        return {i: bytes(b) for i, b in con.execute("SELECT idx, mp3 FROM clips WHERE conversation = ?", (name,))}


def list_conversations() -> list[str]:
    with closing(_db()) as con:
        return [r[0] for r in con.execute("SELECT name FROM conversations ORDER BY updated_at DESC")]


def load_conversation(name: str) -> Conversation:
    with closing(_db()) as con:
        room, cast, summary, summarized, memories, seen, world = con.execute(
            "SELECT room, cast_json, summary, summarized, memories_json, seen_json, manifestations_json"
            " FROM conversations WHERE name = ?", (name,)).fetchone()
        history = [Message(*r) for r in con.execute(
            "SELECT speaker, text, kind FROM messages WHERE conversation = ? ORDER BY idx", (name,))]
    return Conversation(room, json.loads(cast), history, summary, summarized, json.loads(memories),
                        json.loads(seen), [Manifestation(**w) for w in json.loads(world or "[]")])


# ------------------------------------------------------------- spoken delivery
DELIVERY_STYLES = {
    "Subtle": (
        "Understated: speed 0.9-1.1, one or two light marks at most, no fillers.\n"
        "Example for 'Look, I just wanted to say sorry.' -> "
        '{"speed": 0.97, "text": "Look, I just wanted to say... sorry."}'
    ),
    "Natural": (
        "Like a real person talking, not an announcer: speed 0.8-1.25, ALWAYS at least two "
        "rhythm marks (pause, ellipsis, breath, a <slow>/<fast> phrase or a soft/emphasis "
        "phrase) for any line over six words, and a filler (um/uh/hmm) wherever the "
        "character would genuinely hesitate.\n"
        "Example for 'Look, I just wanted to say sorry. I really mean it.' -> "
        '{"speed": 0.92, "text": "Look, [pause] I - um - just wanted to say <soft>sorry</soft>. '
        '[breath] <emphasis>I really mean it</emphasis>."}'
    ),
    "Dramatic": (
        "Stage-actor big: speed anywhere 0.7-1.5 with strong contrast between phrases. Use at "
        "least THREE different marks per line (e.g. whisper/soft, long-pause, slow, loud, "
        "sigh, breath, pitch changes) and let the line build or collapse emotionally.\n"
        "Example for 'Look, I just wanted to say sorry. I really mean it.' -> "
        '{"speed": 0.78, "text": "<whisper>Look,</whisper> [long-pause] I just wanted to say... '
        '[exhale] <slow><lower-pitch>sorry</lower-pitch></slow>. [breath] <build-intensity>I really '
        'mean it</build-intensity>."}'
    ),
}

DELIVERY_SYSTEM = (
    "You are a voice director coaching a text-to-speech actor. You get one line a character is "
    "about to say, plus the scene and the character's history. Decide HOW a real person in that "
    "exact moment would say it, so it does not sound read aloud or artificial.\n"
    "Return ONLY JSON: {\"speed\": <number 0.7-1.5>, \"text\": \"<the line with delivery marks>\"}.\n\n"
    "What should drive the delivery:\n"
    "- ENVIRONMENT: loud/dangerous places push people to shout and rush; quiet or intimate places "
    "(library, night, secrets) bring hush and slowness; formal settings are measured.\n"
    "- STATE: panic, anger, excitement, impatience = faster, louder, shorter breaths. Exhaustion, "
    "grief, fear, drunkenness, contempt, menace = slower, softer or lower, with sighs and pauses. "
    "Nervous or unsure characters hesitate and trail off.\n"
    "- HISTORY: use their private notes and recent lines: a character who has been shouted at "
    "speaks smaller; one gaining confidence speeds up; a long-suffering one sounds weary.\n"
    "- LINE: short punchy lines run faster; long reflective ones slow down toward the end.\n\n"
    "Tools:\n"
    "- speed applies to the whole line. For changes INSIDE the line wrap phrases in "
    "<slow>..</slow> or <fast>..</fast>, e.g. rushing a clause then slowing the key words.\n"
    "- Rough / hoarse / gravelly voice: <lower-pitch> plus <soft> or <slow>, with [exhale], [breath] "
    "or [tsk]. Shaky or fragile: <soft> with [breath] and short [pause]s. Shouting: <loud> "
    "(often with <higher-pitch>). Menace or intimacy: <whisper> or <lower-pitch>+<slow>. "
    "Rising excitement: <build-intensity>. Fading out: <decrease-intensity>.\n"
    "- Inline tags: [pause] [long-pause] [laugh] [chuckle] [giggle] [sigh] [breath] [inhale] "
    "[exhale] [tsk] [cry]. Wrapping tags (always closed): soft whisper loud slow fast emphasis "
    "higher-pitch lower-pitch build-intensity decrease-intensity.\n"
    "- Punctuation shapes rhythm: use commas, ellipses (...) and dashes (-) for hesitations, "
    "trailing off and abrupt stops.\n"
    "- You may insert hesitations ONLY from: um, uh, hmm, er, ah.\n"
    "- Turn stage actions in *asterisks* into vocal cues where they make sound (*sighs* -> "
    "[sigh], *whispers* -> <whisper>); otherwise drop them.\n"
    "- NEVER add, remove, reorder or change any other word.\n"
)


def plan_delivery(c: Character, room: Room, convo: Conversation, line: str, config,
                  style: str = "Natural") -> tuple[str, float]:
    """Pick tempo and rhythm for a line from the scene and the character's history.

    Returns (text_with_tags, speed). If the model's markup is invalid or alters the words (after one retry) it falls back to
    the plain spoken words, keeping the pace the director chose.
    """
    plain = speakable(line)
    context = (
        f"Character: {c.name}. Persona: {c.persona}. Behaviour: {c.behavior}\n"
        f"Setting: {room.description}\n"
        + (f"Story so far: {convo.summary}\n" if convo.summary else "")
        + f"{c.name}'s private notes (their mood and history):\n{convo.memories.get(c.name, '(none)')}\n"
        + f"\nRecent lines:\n{_lines(convo.history[-7:-1])}\n\n"
        f"Line to perform (from {c.name}):\n{line}"
    )
    system = DELIVERY_SYSTEM + "\nSTYLE - " + style + ". " + DELIVERY_STYLES[style]
    speed, prompt = 1.0, context
    for attempt in range(2):  # one retry, telling the model what it got wrong
        try:
            raw = _ask_sync("VoiceDirector", system, prompt, config)
            data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
            speed = min(MAX_SPEED, max(MIN_SPEED, float(data.get("speed", speed))))
            marked = clean_delivery(line, str(data.get("text", "")))
        except (ValueError, TypeError, RuntimeError):
            marked = None
        if marked:
            return marked, speed
        prompt = (context + "\n\nYour previous answer was rejected: it changed the spoken words or "
                  "used an invalid or unclosed tag. Keep the words IDENTICAL to the line (only "
                  "um/uh/hmm/er/ah may be added) and use only the allowed tags.")
    return plain, speed  # plain reading, but still at the pace the director chose
