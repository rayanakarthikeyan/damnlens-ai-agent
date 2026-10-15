from pathlib import Path
import pytest
from app.engine import extract
from app.quality import approve, enrich

ROOT = Path(__file__).resolve().parents[1]


def test_review_is_bound_to_data_fingerprint():
    r = extract(ROOT / "samples" / "01_invoice_register.pdf")
    approve(r, "Source checked")
    assert r["quality"]["review_status"] == "reviewed"
    r["tables"][0]["rows"][0]["cells"][0] = "CHANGED"
    assert enrich(r)["quality"]["review_status"] == "pending"


def test_no_data_cannot_be_marked_reviewed():
    r = {
        "sha256": "",
        "tables": [],
        "issues": [],
        "pages": [{"page": 1, "status": "needs_review"}],
        "page_count": 1,
        "edits": [],
    }
    with pytest.raises(ValueError, match="data rows"):
        approve(r)


def test_native_confidence_is_excluded_from_ocr_mean():
    r = extract(ROOT / "samples" / "01_invoice_register.pdf")
    first = r["tables"][0]["rows"][0]
    first.update(method="OCR · grid", confidence=0.75)
    q = enrich(r)["quality"]
    assert (
        q["ocr_rows"] == 1
        and q["ocr_recognition_mean"] == 0.75
        and q["ocr_low_score_rows"] == 1
    )
