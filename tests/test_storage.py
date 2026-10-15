"""Protect the original job/ledger when the filesystem cannot accept a write."""

import json
from pathlib import Path

import pytest

from app.storage import atomic_json


def test_serialization_failure_preserves_existing_ledger(tmp_path):
    path = tmp_path / "ledger.json"
    atomic_json(path, {"requests_used": 1})
    with pytest.raises(ValueError):
        atomic_json(path, {"requests_used": float("nan")})
    assert json.loads(path.read_text()) == {"requests_used": 1}
    assert list(tmp_path.glob("*.tmp")) == []


def test_partial_temporary_write_does_not_replace_existing_state(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    atomic_json(path, {"state": "complete"})
    original = Path.write_text

    def disk_full(target, text, **kwargs):
        original(target, text[:5], **kwargs)
        raise OSError("simulated full disk")

    monkeypatch.setattr(Path, "write_text", disk_full)
    with pytest.raises(OSError, match="full disk"):
        atomic_json(path, {"state": "replacement"})
    assert json.loads(path.read_text()) == {"state": "complete"}
    assert list(tmp_path.glob("*.tmp")) == []


def test_permanent_sharing_lock_is_bounded_and_preserves_state(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    atomic_json(path, {"state": "complete"})
    calls = []

    def locked(*args):
        calls.append(1)
        raise PermissionError("simulated sharing lock")

    monkeypatch.setattr(Path, "replace", locked)
    monkeypatch.setattr("app.storage.time.sleep", lambda *args: None)
    with pytest.raises(PermissionError):
        atomic_json(path, {"state": "replacement"})
    assert len(calls) == 7
    assert json.loads(path.read_text()) == {"state": "complete"}
    assert list(tmp_path.glob("*.tmp")) == []
