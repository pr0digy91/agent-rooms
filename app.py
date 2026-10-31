import html
import json

import streamlit as st
from dotenv import load_dotenv

from player import device_picker, run_player
from sim import (DELIVERY_STYLES, MANIFEST_KINDS, VERSION, Character, Conversation, Message, Room, banish, get_setting,
                 list_conversations, load_clips, load_conversation, load_state, make_config, manifest, next_turn,
                 plan_delivery, safe_error, save_conversation, save_state, set_setting)
from style import avatar_html, color_for, css
from voice import VOICES, default_voice, speak, transcribe

load_dotenv()
st.set_page_config(page_title="Agent Rooms", page_icon="🎭", layout="wide")

if "state" not in st.session_state:
    st.session_state.state = load_state()
    st.session_state.convo = Conversation()
    st.session_state.dark = get_setting("theme", "dark") == "dark"
state = st.session_state.state
esc = html.escape

# Settings that survive a restart (stored as one JSON value in the database).
PREFS = {"auto_respond": False, "speak_aloud": False, "expressive": True, "style": "Natural", "tempo": 1.0,
         "mode": "Director", "prefer_addressed": True, "use_memory": True, "sim_room": None, "sim_cast": None}
if "prefs_loaded" not in st.session_state:
    try:
        saved = json.loads(get_setting("prefs", "{}"))
    except ValueError:
        saved = {}
    for k, default in PREFS.items():
        v = saved.get(k, default)
        if v is not None:
            st.session_state[k] = v
    st.session_state.prefs_loaded = True
for k, default in PREFS.items():  # a widget that lost its state must never fall back to its own default
    if default is not None:
        st.session_state.setdefault(k, default)

# ------------------------------------------------------------------ header
head_l, head_r = st.columns([5, 1], vertical_alignment="center")
head_l.markdown(
    '<div class="brand"><div class="logo">🎭</div><div><h1>Agent Rooms</h1>'
    f"<p>Characters and rooms that talk back. Powered by AG2 and Grok. v{VERSION}</p></div></div>",
    unsafe_allow_html=True,
)
dark = head_r.toggle(":material/dark_mode: Dark mode", key="dark")
if get_setting("theme", "dark") != ("dark" if dark else "light"):
    set_setting("theme", "dark" if dark else "light")
st.html(css("dark" if dark else "light"))  # style-only HTML takes no space in the layout
with st.container(key="player"):
    run_player()  # shared audio player; the first click/keypress unlocks browser autoplay

tab_sim, tab_chars, tab_rooms = st.tabs([":material/forum: Simulation", ":material/group: Characters", ":material/home: Rooms"])

# ---------------------------------------------------------------- Characters
with tab_chars:
    with st.expander(":material/person_add: New character"):
        with st.form("add_char", clear_on_submit=True, border=False):
            f1, f2 = st.columns([2, 1])
            name = f1.text_input("Name")
            voice = f2.selectbox("Voice (when speaking aloud)", VOICES)
            persona = st.text_area("Persona (who they are)", height=80)
            behavior = st.text_area("Behaviour (how they act and talk)", height=80)
            if st.form_submit_button("Add character", type="primary") and name.strip():
                if name.strip() in [c.name for c in state.characters]:
                    st.warning("There is already a character with that name.")
                else:
                    state.characters.append(Character(name.strip(), persona, behavior, voice))
                    save_state(state)
                    st.rerun()
    cols = st.columns(3)
    for i, c in enumerate(state.characters):
        with cols[i % 3], st.container(key=f"card_char_{i}"):
            st.markdown(
                f'<div class="card-head">{avatar_html(c.name, 44)}<div><div class="t">{esc(c.name)}</div>'
                f'<div class="s">🔊 voice: {esc(c.voice)}</div></div></div>'
                f'<div class="persona">{esc(c.persona) or "<i>No persona yet.</i>"}</div>',
                unsafe_allow_html=True,
            )
            with st.expander("Edit"):  # keyed by name: index keys hand a deleted card's text to the next one
                c.persona = st.text_area("Persona", c.persona, key=f"cp_{c.name}", height=80)
                c.behavior = st.text_area("Behaviour", c.behavior, key=f"cb_{c.name}", height=80)
                c.voice = st.selectbox("Voice", VOICES, index=VOICES.index(c.voice) if c.voice in VOICES else 0,
                                       key=f"cv_{c.name}")
                b1, b2 = st.columns(2)
                if b1.button("Save", key=f"cs{i}", type="primary", use_container_width=True):
                    save_state(state)
                    st.toast("Saved")
                if b2.button("Delete", key=f"cd{i}", use_container_width=True):
                    state.characters.pop(i)
                    save_state(state)
                    st.rerun()

# --------------------------------------------------------------------- Rooms
with tab_rooms:
    with st.expander(":material/add_home: New room"):
        with st.form("add_room", clear_on_submit=True, border=False):
            rname = st.text_input("Room name")
            desc = st.text_area("Environment / scenario", height=100)
            rules = st.text_area("Rules (optional)", height=60)
            if st.form_submit_button("Add room", type="primary") and rname.strip():
                if rname.strip() in [r.name for r in state.rooms]:
                    st.warning("There is already a room with that name.")
                else:
                    state.rooms.append(Room(rname.strip(), desc, rules))
                    save_state(state)
                    st.rerun()
    cols = st.columns(3)
    for i, r in enumerate(state.rooms):
        with cols[i % 3], st.container(key=f"card_room_{i}"):
            st.markdown(
                f'<div class="card-head"><div class="logo-sm" style="font-size:28px">🏠</div><div>'
                f'<div class="t">{esc(r.name)}</div><div class="s">{"📜 has rules" if r.rules else "no special rules"}</div>'
                f'</div></div><div class="persona">{esc(r.description) or "<i>No description yet.</i>"}</div>',
                unsafe_allow_html=True,
            )
            with st.expander("Edit"):
                r.description = st.text_area("Environment", r.description, key=f"rd_{r.name}", height=100)
                r.rules = st.text_area("Rules", r.rules, key=f"rr_{r.name}", height=60)
                b1, b2 = st.columns(2)
                if b1.button("Save", key=f"rs{i}", type="primary", use_container_width=True):
                    save_state(state)
                    st.toast("Saved")
                if b2.button("Delete", key=f"rx{i}", use_container_width=True):
                    state.rooms.pop(i)
                    save_state(state)
                    st.rerun()


# ---------------------------------------------------------------- Simulation
def _load_convo(name: str) -> None:
    c = load_conversation(name)
    st.session_state.convo = c
    st.session_state.clips = load_clips(name)
    st.session_state.sim_room = c.room
    st.session_state.sim_cast = [n for n in c.cast if n in {x.name for x in state.characters}]


REACTIONS = ["Everyone reacts", "One character reacts", "Just introduce it"]


def _do_manifest() -> None:
    """Button callback: bring the thing into the world and clear the form."""
    ss = st.session_state
    name = (ss.get("m_name") or "").strip()
    if not name:
        st.toast("Give it a name first.")
        return
    manifest(ss.convo, ss.m_kind, name, ss.get("m_desc") or "", ss.m_conviction)
    ss.pending_react = ss.m_react  # the room reacts after this run's layout is built
    ss.m_name = ss.m_desc = ""


def _do_banish(index: int) -> None:
    banish(st.session_state.convo, index)


with tab_sim:
    if not state.rooms or len(state.characters) < 2:
        st.info("You need at least one room and two characters.")
        st.stop()
    convo: Conversation = st.session_state.convo
    clips: dict[int, bytes] = st.session_state.setdefault("clips", {})  # message index -> mp3
    char_names = [c.name for c in state.characters]
    ss = st.session_state
    if ss.get("sim_room") not in [r.name for r in state.rooms]:
        ss.pop("sim_room", None)  # saved room was deleted
    chosen = ss.get("sim_cast")
    ss["sim_cast"] = [n for n in (char_names[:3] if chosen is None else chosen) if n in char_names]
    player = state.player

    left, right = st.columns([1, 2.6], gap="large")

    # ------------------------------------------------------------ left panel
    with left:
        with st.container(key="scene"):
            st.markdown('<div class="section-label">Scene</div>', unsafe_allow_html=True)
            room = state.rooms[[r.name for r in state.rooms].index(
                st.selectbox("Room", [r.name for r in state.rooms], key="sim_room"))]
            st.markdown(f'<div class="scene-card">{esc(room.description) or "No description."}</div>',
                        unsafe_allow_html=True)
            names = st.multiselect("Who is in the room?", char_names, key="sim_cast")
            mode = st.selectbox("Who speaks next?", ["Director", "Round robin", "Random"], key="mode",
                                help="Director = Grok decides who'd most naturally reply.")
        cast = [c for c in state.characters if c.name in names]

        with st.container(key="manifestbox"):
            st.markdown('<div class="section-label">Manifestation box</div>', unsafe_allow_html=True)
            kind = st.selectbox("What are you bringing into the world?", list(MANIFEST_KINDS), key="m_kind")
            st.caption(MANIFEST_KINDS[kind].capitalize() + ".")
            st.text_input("Name", key="m_name", placeholder="e.g. The Obsidian Key")
            st.text_area("Details (optional)", key="m_desc", height=68,
                         placeholder="What does it look like, do, or mean?")
            st.slider("Conviction", 0, 100, 50, key="m_conviction",
                      help="How firmly everyone believes in this, and in what it claims. 100 = accepted as plain "
                           "truth; low = they doubt it, ask for proof and push back in their own way.")
            st.selectbox("How does the room respond?", REACTIONS, key="m_react")
            st.button(":material/auto_awesome: Manifest", type="primary", use_container_width=True,
                      on_click=_do_manifest)
            live = [(i, w) for i, w in enumerate(convo.manifestations) if w.active]
            if live:
                st.markdown('<div class="section-label" style="margin-top:.9rem">In the scene</div>',
                            unsafe_allow_html=True)
            for i, w in live:
                r1, r2 = st.columns([5, 1], vertical_alignment="center")
                r1.markdown(f'<span class="chip">{esc(w.kind)}</span> <b>{esc(w.name)}</b> <span style="opacity:.6">· belief {w.conviction}</span>', unsafe_allow_html=True)
                r2.button(":material/close:", key=f"banish_{i}", help=f"Banish {w.name}",
                          on_click=_do_banish, args=(i,))

        with st.popover(":material/tune: Options", use_container_width=True):
            prefer_addressed = st.toggle("Whoever is addressed by name replies next", key="prefer_addressed",
                                         help="Overrides the speaker mode when the last message names a character.")
            use_memory = st.toggle("Memory (summary + private notes)", key="use_memory",
                                   help="Costs one extra model call per turn.")
            st.divider()
            speak_aloud = st.toggle(":material/volume_up: Speak replies aloud", key="speak_aloud",
                                    help="Each reply plays automatically in the character's own voice.")
            expressive = st.toggle(":material/theater_comedy: Expressive delivery", key="expressive", disabled=not speak_aloud,
                                   help="Tempo and rhythm from the scene and each character's history. "
                                        "One extra model call per spoken line.")
            style = st.selectbox("Delivery style", list(DELIVERY_STYLES), key="style",
                                 disabled=not (speak_aloud and expressive),
                                 help="Subtle = understated, Natural = like a real person, Dramatic = stage actor.")
            tempo = st.slider("Base tempo", 0.8, 1.25, step=0.05, key="tempo", disabled=not speak_aloud,
                              help="Scales every character's speed on top of the scene-based pacing.")

        with st.expander(":material/headset_mic: Audio devices"):
            st.caption("Pick your microphone and headphones. Saved in this browser.")
            device_picker()

        with st.expander(f":material/account_circle: You: {player.name}"):
            player.name = st.text_input("Your name", player.name).strip() or "You"
            player.persona = st.text_area("Your persona (who you are)", player.persona, height=80)
            player.behavior = st.text_area("Your nature (how you act and talk)", player.behavior, height=80)
            snapshot = (player.name, player.persona, player.behavior)
            if st.session_state.get("player_snapshot", snapshot) != snapshot:
                save_state(state)  # autosave on edit
                st.caption("✓ Saved")
            st.session_state.player_snapshot = snapshot
            if player.name in char_names:
                st.warning("Your name matches a character's name. Pick a different one.")

    # ----------------------------------------------------------- right panel
    with right:
        st.markdown(
            f'<div class="room-title"><span class="t">{esc(room.name)}</span>'
            f'<span class="chip">{len(cast)} in the room</span>'
            f'<span class="chip muted">{esc(mode)}</span>'
            + ('<span class="chip muted">Voice on</span>' if speak_aloud else "")
            + "</div>",
            unsafe_allow_html=True,
        )
        t1, t2, _, t3, t4 = st.columns([3.2, 1.2, 0.3, 1.4, 1.7], vertical_alignment="center")
        auto = t1.checkbox("Auto-respond when I speak", key="auto_respond",
                           help="After you send a message, the room replies right away (no need to press Next turn).")
        prefs = {k: st.session_state.get(k) for k in PREFS}
        if get_setting("prefs", "") != json.dumps(prefs):
            set_setting("prefs", json.dumps(prefs))
        if t2.button(":material/delete: Reset", use_container_width=True):
            st.session_state.convo = Conversation()
            st.session_state.clips = {}
            st.rerun()
        steps = (1 if t3.button(":material/play_arrow: Next", disabled=auto, use_container_width=True, type="primary")
                 else 5 if t4.button(":material/fast_forward: Run 5 turns", use_container_width=True) else 0)

        box = st.container(height=520, border=False, autoscroll=True, key="chatbox")  # filled below
        submitted = st.chat_input(f"Say something to the room as {player.name} (type or use the mic)",
                                  accept_audio=True)
        error_slot = st.empty()
        nudge = (submitted.text or "").strip() if submitted else ""
        if submitted and not nudge and submitted.get("audio"):  # recorded with the mic button
            try:
                with st.spinner("Transcribing..."):
                    nudge = transcribe(submitted["audio"].getvalue())
            except Exception as e:
                error_slot.error(f"Couldn't transcribe: {safe_error(e)}")
        if nudge:
            convo.history.append(Message(player.name, nudge))
            if auto:
                steps = 1
        react = st.session_state.pop("pending_react", None)  # set when something was just manifested
        reactors = list(cast) if react == REACTIONS[0] else None
        if react == REACTIONS[0]:
            steps = len(cast)
        elif react == REACTIONS[1]:
            steps = 1

        def show(m: Message, mp3: bytes | None = None):
            """Render one message in the chat window; returns a slot its audio player can fill later."""
            if m.kind in ("manifest", "banish"):
                name, _, desc = m.text.partition("\n")
                head = "Manifested" if m.kind == "manifest" else "Vanished"
                with box:
                    st.markdown(
                        f'<div class="world {m.kind}"><div class="w-label">{head} · {esc(m.speaker)}</div>'
                        f'<div class="w-name">{esc(name)}</div>'
                        + (f'<div class="w-desc">{esc(desc)}</div>' if desc else "") + "</div>",
                        unsafe_allow_html=True)
                return box.empty()
            is_human = m.speaker not in char_names
            with box.chat_message("user" if is_human else "assistant"):
                st.markdown(f'<div class="msg-head">{avatar_html(m.speaker, 24)}'
                            f'<span class="nm" style="{"" if is_human else "color:color-mix(in srgb," + color_for(m.speaker) + " 68%,var(--text))"}">'
                            f"{esc(m.speaker)}</span></div>", unsafe_allow_html=True)
                st.markdown(m.text)
                slot = st.empty()
                if mp3:
                    slot.audio(mp3, format="audio/mpeg")
            return slot

        if not convo.history:
            with box:
                st.markdown('<div class="scene-card" style="margin:1rem">No messages yet. Press <b>Next</b> '
                            "to let the characters start, or say something below.</div>", unsafe_allow_html=True)
        for i, m in enumerate(convo.history):
            show(m, clips.get(i))

        if steps and len(cast) < 2:
            st.warning("Pick at least two characters.")
        elif steps:
            convo.room, convo.cast = room.name, names
            by_name = {c.name: c for c in state.characters}
            try:
                config = make_config()
                for _ in range(steps):
                    with box, st.spinner("Thinking..."):
                        msg = next_turn(room, cast, convo, mode, config, use_memory, player, prefer_addressed,
                                        candidates=reactors)
                    if reactors is not None:  # everyone reacts once
                        reactors = [c for c in reactors if c.name != msg.speaker]
                    slot = show(msg)  # text appears immediately; the audio player fills in below it
                    if not speak_aloud:
                        continue
                    speaker = by_name.get(msg.speaker)
                    try:
                        with box, st.spinner(f"{msg.speaker} is finding their voice..."):
                            text, speed = (plan_delivery(speaker, room, convo, msg.text, config, style)
                                           if expressive and speaker else (msg.text, 1.0))
                            mp3 = speak(text, speaker.voice if speaker else default_voice(), speed * tempo,
                                        marked_up=expressive)
                        if mp3:
                            clips[len(convo.history) - 1] = mp3
                            slot.audio(mp3, format="audio/mpeg")  # manual player for replays
                            run_player(mp3)  # autoplay through the shared, queued player
                    except Exception as e:
                        st.warning(f"Couldn't voice {msg.speaker}: {safe_error(e)}")
            except Exception as e:
                st.error(safe_error(e))

        with st.expander(":material/psychology: Memory: summary and private notes"):
            st.markdown("**Story summary**")
            st.write(convo.summary or "_Nothing summarized yet (kicks in after ~30 messages)._")
            for n, mem in convo.memories.items():
                st.markdown(f"**{n}'s private notes**")
                st.write(mem)

        with st.expander(":material/save: Save / load conversation"):
            s1, s2 = st.columns(2)
            saved = list_conversations()
            save_name = s1.text_input("Save as", value=convo.room and f"{convo.room} chat" or "my chat")
            replacing = save_name.strip() in saved
            if replacing:
                s1.caption("A saved conversation already has this name.")
            if s1.button("Overwrite" if replacing else "Save", type="primary") and convo.history:
                convo.room, convo.cast = room.name, names
                save_conversation(save_name, convo, clips)
                st.toast(f"Saved '{save_name}'")
                saved = list_conversations()
            pick = s2.selectbox("Saved conversations", saved) if saved else None
            if pick:
                s2.button("Load", on_click=_load_convo, args=(pick,))
