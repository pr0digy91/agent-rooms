"""Who speaks next, and what they are told. All offline: the model is scripted or captured."""

from ag2.testing import TestConfig

import sim

MARA = sim.Character("Captain Mara", "a captain", "gruff", "ara")
PIP = sim.Character("Pip", "a mechanic", "eager", "leo")
VOSS = sim.Character("Dr. Voss", "a scientist", "suspicious", "rex")
CAST = [MARA, PIP, VOSS]
ROOM = sim.Room("Mess Hall", "A cramped mess hall")
PLAYER = sim.Character("Garunya", "a visitor", "calm")


def capture(monkeypatch, answer="line"):
    """Replace the model call; returns the list of (name, system, prompt) it received."""
    calls = []

    def fake(name, system, prompt, config):
        calls.append((name, system, prompt))
        return answer

    monkeypatch.setattr(sim, "_ask_sync", fake)
    return calls


def test_next_turn_appends_the_reply():
    convo = sim.Conversation()
    msg = sim.next_turn(ROOM, CAST, convo, "Round robin", TestConfig("Hold steady."), use_memory=False)
    assert (msg.speaker, msg.text) == ("Captain Mara", "Hold steady.")
    assert convo.history == [msg]


def test_a_reply_prefixed_with_the_speakers_name_is_cleaned():
    convo = sim.Conversation()
    msg = sim.next_turn(ROOM, CAST, convo, "Round robin", TestConfig("Captain Mara: Hold steady."), use_memory=False)
    assert msg.text == "Hold steady."


def test_round_robin_moves_to_the_next_character():
    history = [sim.Message("Captain Mara", "Report.")]
    assert sim.pick_speaker("Round robin", CAST, history, None).name == "Pip"


def test_addressed_character_speaks_next_in_any_mode():
    history = [sim.Message("Garunya", "Voss, what do you see?")]
    assert sim.pick_speaker("Round robin", CAST, history, None).name == "Dr. Voss"


def test_addressing_can_be_turned_off():
    history = [sim.Message("Captain Mara", "Voss, what do you see?")]
    assert sim.pick_speaker("Round robin", CAST, history, None, prefer_addressed=False).name == "Pip"


def test_titles_do_not_count_as_a_name():
    assert sim.addressed_character(sim.Message("Pip", "Ask the doctor about it"), CAST) is None


def test_director_is_shown_the_transcript(monkeypatch):
    calls = capture(monkeypatch, answer="Pip")
    history = [sim.Message("Captain Mara", "The relays are failing.")]
    assert sim.pick_speaker("Director", CAST, history, None).name == "Pip"
    assert "The relays are failing." in calls[0][2]


def test_the_director_is_not_paid_to_choose_from_one_name(monkeypatch):
    calls = capture(monkeypatch)
    history = [sim.Message("Pip", "Anyone there?")]
    assert sim.pick_speaker("Director", [VOSS], history, None).name == "Dr. Voss"
    assert calls == []


def test_candidates_limit_who_can_react(monkeypatch):
    capture(monkeypatch)
    convo = sim.Conversation()
    sim.manifest(convo, "Idea", "A rumour")
    msg = sim.next_turn(ROOM, CAST, convo, "Random", None, use_memory=False, candidates=[VOSS])
    assert msg.speaker == "Dr. Voss"


def test_a_manifestation_asks_for_a_reaction_and_appears_in_the_system_prompt(monkeypatch):
    calls = capture(monkeypatch)
    convo = sim.Conversation()
    sim.manifest(convo, "Artifact", "The Obsidian Key", "hums softly")
    sim.next_turn(ROOM, CAST, convo, "Round robin", None, use_memory=False, player=PLAYER)
    _, system, prompt = calls[0]
    assert "The Obsidian Key" in system and "hums softly" in system
    assert "JUST manifested" in prompt


def test_firm_belief_is_repeated_on_every_turn(monkeypatch):
    calls = capture(monkeypatch)
    convo = sim.Conversation(history=[sim.Message("Pip", "Hello")])
    sim.manifest(convo, "Artifact", "Baseline map", conviction=97)
    convo.history.append(sim.Message("Pip", "Interesting."))
    sim.next_turn(ROOM, CAST, convo, "Round robin", None, use_memory=False)
    assert "Baseline map is accepted as true" in calls[0][2]
