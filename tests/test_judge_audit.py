"""End-to-end regressions from the judge audit, using differently styled PDFs."""

import pymupdf as fitz
import pytest

from app.engine import extract, record, stitch, validate
from scripts.judge_audit import cases


AUDIT_CASES = list(cases())


@pytest.mark.parametrize(
    "name,data,expected,headers", AUDIT_CASES, ids=[c[0] for c in AUDIT_CASES]
)
def test_varied_development_documents(tmp_path, name, data, expected, headers):
    path = tmp_path / f"{name}.pdf"
    path.write_bytes(data)
    result = extract(path)
    actual = [r["cells"] for t in result["tables"] for r in t["rows"]]
    assert actual == expected
    assert all(t["headers"] == headers for t in result["tables"])
    assert len(result["tables"]) == (1 if expected else 0)
    if "borderless" in name:
        assert "alignment_review" in {i["kind"] for i in result["issues"]}
    if not expected:
        assert "page_review" in {i["kind"] for i in result["issues"]}
    with fitz.open(path) as source:
        for table in result["tables"]:
            for row in table["rows"]:
                box = fitz.Rect(row["bbox"])
                page = source[row["page"] - 1]
                assert not box.is_empty
                assert box.x0 >= -2 and box.y0 >= -2
                assert box.x1 <= page.rect.width + 2 and box.y1 <= page.rect.height + 2


def test_pdf_rotation_evidence_matches_original_viewer(tmp_path):
    data = dict((n, d) for n, d, _, _ in cases())["pdf_rotation_90"]
    path = tmp_path / "rotated.pdf"
    path.write_bytes(data)
    result = extract(path)
    with fitz.open(path) as source:
        page = source[0]
        row = result["tables"][0]["rows"][0]
        text_box = page.search_for("P001")[0] * page.rotation_matrix
        assert fitz.Rect(row["bbox"]).intersects(text_box)
        assert result["pages"][0]["width"] == page.rect.width


def test_bootstrap_healthy_runtime_never_installs(monkeypatch):
    import setup_judges as bootstrap

    calls = []
    monkeypatch.setattr(
        bootstrap.sys, "argv", ["setup_judges.py", "--setup-only", "--offline"]
    )
    monkeypatch.setattr(bootstrap, "check_assets", lambda: None)
    monkeypatch.setattr(bootstrap, "runtime_ready", lambda python: True)
    monkeypatch.setattr(bootstrap.subprocess, "run", lambda *a, **kw: calls.append(a))
    assert bootstrap.main() == 0
    assert not calls


def test_bootstrap_missing_offline_runtime_is_actionable(monkeypatch):
    import setup_judges as bootstrap

    monkeypatch.setattr(bootstrap.sys, "argv", ["setup_judges.py", "--offline"])
    monkeypatch.setattr(bootstrap, "check_assets", lambda: None)
    monkeypatch.setattr(bootstrap, "runtime_ready", lambda python: False)
    with pytest.raises(RuntimeError, match="once online"):
        bootstrap.main()


@pytest.mark.parametrize(
    "stated,expected", [("100000.11", True), ("100000.10", False), ("100001.10", True)]
)
def test_totals_detect_cent_errors_even_on_large_amounts(stated, expected):
    rows = [["Item ID", "Amount"], ["A", "100000.00"], ["B", "0.10"], ["TOTAL", stated]]
    tables = stitch(
        [
            {
                "rows": [
                    record(row, 1, [20, i * 20, 200, i * 20 + 20], "Native PDF")
                    for i, row in enumerate(rows)
                ],
                "bbox": [20, 0, 200, 100],
                "width": 300,
            }
        ]
    )
    assert any(i["kind"] == "total_mismatch" for i in validate(tables)) is expected


def test_decimal_validation_avoids_float_precision_loss():
    rows = [
        ["Item ID", "Amount"],
        ["A", "9007199254740992.00"],
        ["B", "0.01"],
        ["TOTAL", "9007199254740992.00"],
    ]
    tables = stitch(
        [
            {
                "rows": [
                    record(row, 1, [20, i * 20, 200, i * 20 + 20], "Native PDF")
                    for i, row in enumerate(rows)
                ],
                "bbox": [20, 0, 200, 100],
                "width": 300,
            }
        ]
    )
    assert "total_mismatch" in {i["kind"] for i in validate(tables)}
