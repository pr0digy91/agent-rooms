"""The delivery validator: marked-up speech may change how a line sounds, never what it says."""

import pytest

import voice

LINE = "Look, I am sorry."


def test_actions_are_not_spoken():
    assert voice.speakable("*sighs deeply* I am  sorry. *leaves*") == "I am sorry."


@pytest.mark.parametrize("marked", [
    "Look, [pause] I am sorry.",
    "Look, I am <soft>sorry</soft>.",
    "<slow>Look,</slow> [breath] I am <emphasis>sorry</emphasis>.",
    "Look, um, I am sorry.",
    "LOOK I am sorry",
])
def test_valid_delivery_is_accepted(marked):
    assert voice.clean_delivery(LINE, marked) == marked


@pytest.mark.parametrize("marked", [
    "Look, I am very sorry.",  # a word added
    "Look, I am.",  # a word lost
    "Look, [shout] I am sorry.",  # unknown inline tag
    "Look, <angry>I am sorry</angry>.",  # unknown wrapping tag
    "Look, <soft>I am sorry.",  # never closed
    "Look, </soft>I am sorry.",  # closed before opened
    "<soft><slow>Look,</soft></slow> I am sorry.",  # crossed
])
def test_invalid_delivery_is_rejected(marked):
    assert voice.clean_delivery(LINE, marked) is None


def test_actions_in_the_original_are_ignored():
    assert voice.clean_delivery("*sighs* I am sorry.", "I am [pause] sorry.") == "I am [pause] sorry."


def test_default_voice_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("XAI_DEFAULT_VOICE", "rex")
    assert voice.default_voice() == "rex"


def test_a_missing_key_is_reported_clearly(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="XAI_API_KEY"):
        voice._headers()
