"""Guards for the mistakes that cannot be taken back once the repository is public."""

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

import sim

ROOT = Path(__file__).parent.parent


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def test_no_tracked_file_holds_a_key():
    leaks = [name for name in git("ls-files").stdout.split("\n")
             if name and re.search(rb"xai-[A-Za-z0-9]{20,}", (ROOT / name).read_bytes())]
    assert leaks == []


def test_the_example_settings_stay_empty():
    assert re.search(r"(?m)^XAI_API_KEY=$", (ROOT / ".env.example").read_text())


@pytest.mark.parametrize("path", [".env", ".env.local", ".streamlit/secrets.toml", "agent_rooms.db", "state.json"])
def test_private_files_are_ignored(path):
    assert git("check-ignore", "-q", path).returncode == 0


def test_the_example_settings_are_not_ignored():
    assert git("check-ignore", "-q", ".env.example").returncode == 1


def test_the_server_stays_on_this_machine():
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())
    assert config["server"]["address"] == "localhost"


def test_errors_shown_on_the_page_hide_the_key(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "not-shaped-like-a-key")
    shown = sim.safe_error(RuntimeError("config=not-shaped-like-a-key, echoed xai-abc123secret"))
    assert "not-shaped-like-a-key" not in shown and "abc123secret" not in shown
    assert shown.startswith("RuntimeError: ")


def test_errors_without_a_key_still_read_normally(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert sim.safe_error(ValueError("bad value")) == "ValueError: bad value"


def test_the_version_comes_from_pyproject():
    assert sim.VERSION == tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
