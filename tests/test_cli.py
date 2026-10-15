"""CLI contracts: protect source, workbook and the billable-request ledger."""

import json
import sys

import pytest

import convert


@pytest.mark.parametrize("collision", ["source.pdf", "result.xlsx", "result.json"])
def test_cloud_ledger_cannot_collide_with_any_output(
    tmp_path, monkeypatch, capsys, collision
):
    source, output = tmp_path / "source.pdf", tmp_path / "result.xlsx"
    ledger = tmp_path / collision
    ledger.write_text('{"requests_used": 1}', encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "convert.py",
            str(source),
            "-o",
            str(output),
            "--json",
            "--workflow",
            "gemini",
            "--allow-cloud",
            "--gemini-ledger",
            str(ledger),
        ],
    )
    monkeypatch.setattr(
        convert,
        "run",
        lambda *a, **k: pytest.fail("Conversion started with colliding paths"),
    )
    with pytest.raises(SystemExit) as error:
        convert.main()
    assert error.value.code == 2
    assert "must differ" in capsys.readouterr().err
    assert json.loads(ledger.read_text()) == {"requests_used": 1}


def test_output_extension_cannot_overwrite_workbook_with_json(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "convert.py",
            str(tmp_path / "source.pdf"),
            "-o",
            str(tmp_path / "result.json"),
            "--json",
        ],
    )
    with pytest.raises(SystemExit) as error:
        convert.main()
    assert error.value.code == 2
    assert ".xlsx extension" in capsys.readouterr().err


def test_unwritable_export_exits_cleanly(tmp_path, monkeypatch, capsys):
    output = tmp_path / "result.xlsx"
    monkeypatch.setattr(
        sys, "argv", ["convert.py", str(tmp_path / "source.pdf"), "-o", str(output)]
    )
    monkeypatch.setattr(convert, "load_environment", lambda *a: None)
    monkeypatch.setattr(convert, "run", lambda *a, **k: {})
    monkeypatch.setattr(convert, "xlsx", lambda *a: b"workbook")
    output.mkdir()  # Cannot replace a directory with a workbook on any platform.
    with pytest.raises(SystemExit) as error:
        convert.main()
    assert error.value.code == 1
    assert "Conversion failed" in capsys.readouterr().err
