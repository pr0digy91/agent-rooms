"""Manifestations: what enters the shared world, and how firmly it is believed."""

import pytest

import sim


def conviction_prompt(conviction):
    convo = sim.Conversation()
    sim.manifest(convo, "Artifact", "Baseline map", "shows a safe crossing", conviction)
    return sim._system_prompt(sim.Character("Voss", "a scientist", "suspicious"), sim.Room("Lab", "A lab"), [], "", "",
                              None, convo.manifestations)


def test_manifest_records_the_item_and_a_world_event():
    convo = sim.Conversation()
    msg = sim.manifest(convo, "Artifact", "  The Key  ", " It hums ", 80)
    assert convo.manifestations == [sim.Manifestation("Artifact", "The Key", "It hums", True, 80)]
    assert (msg.speaker, msg.text, msg.kind) == ("Artifact", "The Key\nIt hums", "manifest")
    assert convo.history == [msg]


def test_banish_removes_it_from_the_prompt_and_logs_the_event():
    convo = sim.Conversation()
    sim.manifest(convo, "Artifact", "The Key")
    msg = sim.banish(convo, 0)
    assert msg.kind == "banish"
    assert convo.manifestations[0].active is False
    assert sim._world_block(convo.manifestations) == ""


@pytest.mark.parametrize("index", [-1, 1])
def test_banishing_a_missing_item_does_nothing(index):
    convo = sim.Conversation()
    sim.manifest(convo, "Idea", "x")
    assert sim.banish(convo, index) is None
    assert len(convo.history) == 1


def test_banishing_twice_logs_once():
    convo = sim.Conversation()
    sim.manifest(convo, "Idea", "x")
    sim.banish(convo, 0)
    assert sim.banish(convo, 0) is None


def test_world_events_are_labelled_in_the_transcript():
    convo = sim.Conversation()
    sim.manifest(convo, "Artifact", "Key", "It hums")
    sim.banish(convo, 0)
    text = sim._lines(convo.history)
    assert "[WORLD EVENT: Artifact suddenly manifests] Key: It hums" in text
    assert "[WORLD EVENT: this suddenly vanishes] Key" in text


@pytest.mark.parametrize("conviction", [85, 97, 100])
def test_high_conviction_overrides_persona_and_comes_after_memory(conviction):
    prompt = conviction_prompt(conviction)
    assert "BELIEF RULE (overrides your personality" in prompt
    assert prompt.index("BELIEF RULE") > prompt.index("How you behave")


@pytest.mark.parametrize("conviction", [16, 50, 84])
def test_middle_conviction_leaves_it_to_the_character(conviction):
    assert "BELIEF RULE" not in conviction_prompt(conviction)


@pytest.mark.parametrize("conviction", [0, 15])
def test_low_conviction_makes_them_resist(conviction):
    assert "you do not believe what" in conviction_prompt(conviction)


def test_a_banished_item_no_longer_binds_anyone():
    convo = sim.Conversation()
    sim.manifest(convo, "Artifact", "Key", conviction=100)
    sim.banish(convo, 0)
    assert sim._belief_rules(convo.manifestations) == ""


def test_each_item_keeps_its_own_conviction():
    convo = sim.Conversation()
    sim.manifest(convo, "Artifact", "Map", conviction=100)
    sim.manifest(convo, "Idea", "Rumour", conviction=5)
    rules = sim._belief_rules(convo.manifestations)
    assert '"Map" is fully established truth' in rules
    assert 'what "Rumour" claims' in rules
