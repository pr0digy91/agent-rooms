"""The Streamlit app, driven headless. No test here reaches a model."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import sim

APP = str(Path(__file__).parent.parent / "app.py")


def open_app():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    return at


def button(at, text):
    return next(b for b in at.button if text in b.label)


@pytest.fixture
def app():
    return open_app()


def manifest(at, name, conviction=50, react="Just introduce it"):
    at.text_input(key="m_name").set_value(name).run()
    at.slider(key="m_conviction").set_value(conviction).run()
    at.selectbox(key="m_react").set_value(react).run()
    button(at, "Manifest").click().run()
    assert not at.exception


def test_the_app_opens_with_defaults(app):
    assert app.session_state.tempo == 1.0
    assert app.session_state.style == "Natural"
    assert app.checkbox(key="auto_respond").value is False


def test_settings_survive_a_new_session(app):
    app.checkbox(key="auto_respond").check().run()
    app.toggle(key="speak_aloud").set_value(True).run()
    app.selectbox(key="style").set_value("Dramatic").run()
    app.slider(key="tempo").set_value(1.15).run()
    app.multiselect(key="sim_cast").set_value(["Pip", "Dr. Voss"]).run()

    fresh = open_app()
    assert fresh.checkbox(key="auto_respond").value is True
    assert fresh.toggle(key="speak_aloud").value is True
    assert fresh.selectbox(key="style").value == "Dramatic"
    assert fresh.slider(key="tempo").value == 1.15
    assert fresh.multiselect(key="sim_cast").value == ["Pip", "Dr. Voss"]


def test_a_saved_room_that_was_deleted_falls_back(app):
    state = sim.load_state()
    state.rooms = state.rooms[1:]
    sim.save_state(state)
    assert open_app().selectbox(key="sim_room").value == state.rooms[0].name


def test_manifesting_adds_a_world_card_with_its_conviction(app):
    manifest(app, "The Obsidian Key", conviction=97)
    convo = app.session_state.convo
    assert convo.manifestations[0].name == "The Obsidian Key"
    assert convo.manifestations[0].conviction == 97
    assert any('class="world manifest"' in m.value for m in app.markdown)
    assert app.text_input(key="m_name").value == ""


def test_a_blank_name_manifests_nothing(app):
    button(app, "Manifest").click().run()
    assert not app.exception
    assert app.session_state.convo.manifestations == []


def test_the_manifest_button_is_ready_before_the_name_is_committed(app):
    # A text box only commits when it loses focus, so a disabled button would swallow the first click.
    assert not button(app, "Manifest").disabled


def test_the_version_is_on_the_page(app):
    assert any(f"v{sim.VERSION}" in m.value for m in app.markdown)


def test_deleting_a_character_leaves_the_others_text_alone(app):
    before = sim.load_state().characters
    app.text_area(key="cp_Captain Mara").input("An edit that goes with her").run()
    app.button(key="cd0").click().run()
    app.button(key="cs0").click().run()
    assert sim.load_state().characters == before[1:]


def test_deleting_a_room_leaves_the_others_text_alone(app):
    before = sim.load_state().rooms
    app.text_area(key="rd_Starship Mess Hall").input("An edit that goes with it").run()
    app.button(key="rx0").click().run()
    app.button(key="rs0").click().run()
    assert sim.load_state().rooms == before[1:]


def test_a_character_name_cannot_be_used_twice(app):
    next(t for t in app.text_input if t.label == "Name" and not t.key).input("Pip")
    button(app, "Add character").click().run()
    assert not app.exception
    assert [c.name for c in app.session_state.state.characters].count("Pip") == 1
    assert app.warning


def test_a_room_name_cannot_be_used_twice(app):
    next(t for t in app.text_input if t.label == "Room name").input("Rainy Cafe")
    button(app, "Add room").click().run()
    assert [r.name for r in app.session_state.state.rooms].count("Rainy Cafe") == 1
    assert app.warning


def test_the_cast_can_be_cleared(app):
    app.multiselect(key="sim_cast").set_value([]).run()
    assert app.multiselect(key="sim_cast").value == []


def test_saving_over_an_existing_chat_says_so():
    sim.save_conversation("my chat", sim.Conversation(history=[sim.Message("Pip", "Hi")]))
    assert any(b.label == "Overwrite" for b in open_app().button)


def test_banishing_shows_a_vanished_card(app):
    manifest(app, "The Obsidian Key")
    next(b for b in app.button if b.key == "banish_0").click().run()
    assert not app.exception
    assert any('class="world banish"' in m.value for m in app.markdown)
    assert not any(b.key == "banish_0" for b in app.button)


def test_the_empty_chat_hint_goes_when_the_first_turn_starts(app, monkeypatch):
    def turn(room, cast, convo, *args, **kwargs):
        convo.history.append(sim.Message(cast[0].name, "Hold steady."))
        return convo.history[-1]

    monkeypatch.setattr(sim, "make_config", lambda: None)
    monkeypatch.setattr(sim, "next_turn", turn)
    assert any("No messages yet" in m.value for m in app.markdown)
    button(app, "Next").click().run()
    assert not app.exception
    assert any(m.value == "Hold steady." for m in app.markdown)
    assert not any("No messages yet" in m.value for m in app.markdown)


def test_a_manifest_name_is_escaped(app):
    manifest(app, "<script>x</script>")
    assert not any("<script>x" in m.value for m in app.markdown)
