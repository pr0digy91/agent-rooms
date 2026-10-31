"""Every test runs against a throwaway database; nothing here may touch real user data."""

import pytest

import sim


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(sim, "DB_FILE", tmp_path / "test.db")
    monkeypatch.setattr(sim, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(sim, "CONVO_DIR", tmp_path / "conversations")
    return tmp_path
