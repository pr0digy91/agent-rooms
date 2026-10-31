"""SQLite persistence: what the user creates must survive restarts and schema changes."""

import json
import sqlite3

import sim


def test_a_fresh_install_gets_the_example_cast_and_rooms():
    state = sim.load_state()
    assert [c.name for c in state.characters] == [c.name for c in sim.DEFAULT_CHARACTERS]
    assert [r.name for r in state.rooms] == [r.name for r in sim.DEFAULT_ROOMS]


def test_edits_survive_a_reload():
    state = sim.load_state()
    state.characters.append(sim.Character("Nyx", "a thief", "quiet", "sal"))
    state.rooms.append(sim.Room("Vault", "A sealed vault", "No talking"))
    state.player = sim.Character("Garunya", "a visitor", "calm")
    sim.save_state(state)

    again = sim.load_state()
    assert again.characters[-1] == sim.Character("Nyx", "a thief", "quiet", "sal")
    assert again.rooms[-1] == sim.Room("Vault", "A sealed vault", "No talking")
    assert again.player.name == "Garunya"


def test_deleted_examples_stay_deleted():
    state = sim.load_state()
    state.characters = state.characters[:1]
    sim.save_state(state)
    assert len(sim.load_state().characters) == 1


def test_settings_round_trip_and_default():
    assert sim.get_setting("theme", "dark") == "dark"
    sim.set_setting("theme", "light")
    sim.set_setting("theme", "dark")
    assert sim.get_setting("theme") == "dark"


def test_conversation_round_trip():
    convo = sim.Conversation("Vault", ["Pip"], [sim.Message("Pip", "Hi")], "so far", 1, {"Pip": "notes"}, {"Pip": 1})
    sim.manifest(convo, "Artifact", "Key", "old", conviction=90)
    sim.manifest(convo, "Idea", "Doubt")
    sim.banish(convo, 1)
    sim.save_conversation("run", convo)
    assert sim.load_conversation("run") == convo
    assert sim.list_conversations() == ["run"]


def test_clips_are_saved_with_the_conversation():
    convo = sim.Conversation(history=[sim.Message("Pip", "Hi"), sim.Message("Mara", "Yes")])
    sim.save_conversation("run", convo, {1: b"mp3"})
    assert sim.load_clips("run") == {1: b"mp3"}


def test_resaving_replaces_clips_and_ignores_stale_indexes():
    convo = sim.Conversation(history=[sim.Message("Pip", "Hi")])
    sim.save_conversation("run", convo, {0: b"old"})
    sim.save_conversation("run", convo, {0: b"new", 7: b"beyond the end"})
    assert sim.load_clips("run") == {0: b"new"}


def test_an_old_database_is_migrated_in_place():
    with sqlite3.connect(sim.DB_FILE) as con:
        con.executescript("""
            CREATE TABLE characters (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
                                     persona TEXT, behavior TEXT);
            CREATE TABLE conversations (name TEXT PRIMARY KEY, room TEXT, cast_json TEXT, summary TEXT,
                                        summarized INTEGER, memories_json TEXT, seen_json TEXT,
                                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE messages (conversation TEXT NOT NULL, idx INTEGER NOT NULL, speaker TEXT, text TEXT,
                                   PRIMARY KEY (conversation, idx));
            INSERT INTO characters(name, persona, behavior) VALUES ('Old', 'p', 'b');
            INSERT INTO conversations(name, room, cast_json, summary, summarized, memories_json, seen_json)
                VALUES ('old', 'Room', '[]', '', 0, '{}', '{}');
            INSERT INTO messages VALUES ('old', 0, 'Pip', 'hello there');
        """)
    con.close()

    convo = sim.load_conversation("old")
    assert convo.history == [sim.Message("Pip", "hello there", "chat")]
    assert convo.manifestations == []


def test_a_saved_manifestation_from_before_conviction_loads_at_the_default():
    convo = sim.Conversation()
    sim.save_conversation("run", convo)
    with sqlite3.connect(sim.DB_FILE) as con:
        con.execute("UPDATE conversations SET manifestations_json = ?",
                    (json.dumps([{"kind": "Idea", "name": "x", "description": "", "active": True}]),))
    con.close()
    assert sim.load_conversation("run").manifestations[0].conviction == 50


def test_legacy_json_replaces_untouched_examples_once(isolated_storage):
    raw = {"characters": [{"name": "Legacy", "persona": "p", "behavior": "b"}],
           "rooms": [{"name": "Old Room", "description": "d"}],
           "player": {"name": "Me", "persona": "", "behavior": ""}}
    sim.STATE_FILE.write_text(json.dumps(raw))

    state = sim.load_state()
    assert [c.name for c in state.characters] == ["Legacy"]
    assert state.player.name == "Me"

    state.characters.append(sim.Character("New", "p", "b"))
    sim.save_state(state)
    assert len(sim.load_state().characters) == 2  # the import does not run a second time
