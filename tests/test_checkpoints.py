import json
from pathlib import Path

import pytest

from app.checkpoints import PageCheckpoints
from app.engine import extract

ROOT = Path(__file__).resolve().parents[1]


def test_interrupted_extraction_resumes_only_verified_pages(tmp_path, monkeypatch):
    source = ROOT / "samples/01_invoice_register.pdf"
    cache = tmp_path / "checkpoints"

    def interrupt(done, total, message):
        if done == 2 and message == "Inspecting page 3":
            raise RuntimeError("Simulated interruption")

    with pytest.raises(RuntimeError, match="Simulated interruption"):
        extract(source, progress=interrupt, checkpoint_dir=cache)
    assert len(list(cache.glob("page-*.json"))) == 2
    import app.engine as engine

    real = engine.native_tables
    calls = []

    def tracked(page, number):
        calls.append(number)
        return real(page, number)

    monkeypatch.setattr(engine, "native_tables", tracked)
    result = extract(source, checkpoint_dir=cache, resume=True)
    assert calls == [3]
    assert sum(p.get("resumed", False) for p in result["pages"]) == 2
    expected = json.loads((ROOT / "samples/ground_truth.json").read_text())[
        "01_invoice_register.pdf"
    ]
    assert [r["cells"] for r in result["tables"][0]["rows"]] == expected["rows"]


def test_changed_source_and_mode_invalidate_checkpoints(tmp_path):
    source = ROOT / "samples/01_invoice_register.pdf"
    cache = tmp_path / "checkpoints"
    extract(source, checkpoint_dir=cache)
    assert PageCheckpoints(cache, source, False).load(1)
    assert PageCheckpoints(cache, source, True).load(1) is None
    changed = tmp_path / "changed.pdf"
    changed.write_bytes(source.read_bytes() + b"\n% changed source bytes")
    assert PageCheckpoints(cache, changed, False).load(1) is None


def test_corrupt_checkpoint_is_ignored_not_trusted(tmp_path):
    source = ROOT / "samples/01_invoice_register.pdf"
    cache = tmp_path / "checkpoints"
    extract(source, checkpoint_dir=cache)
    path = cache / "page-001.json"
    envelope = json.loads(path.read_text())
    envelope["payload"]["fragments"][0]["rows"][1]["cells"][0] = "CHANGED"
    path.write_text(json.dumps(envelope), encoding="utf-8")
    assert PageCheckpoints(cache, source, False).load(1) is None
    path.write_text("{truncated", encoding="utf-8")
    assert PageCheckpoints(cache, source, False).load(1) is None
