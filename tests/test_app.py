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


def test_a_blank_name_cannot_be_manifested(app):
    assert button(app, "Manifest").disabled


def test_banishing_shows_a_vanished_card(app):
    manifest(app, "The Obsidian Key")
    next(b for b in app.button if b.key == "banish_0").click().run()
    assert not app.exception
    assert any('class="world banish"' in m.value for m in app.markdown)
    assert not any(b.key == "banish_0" for b in app.button)


def test_a_manifest_name_is_escaped(app):
    manifest(app, "<script>x</script>")
    assert not any("<script>x" in m.value for m in app.markdown)
