"""Observable quality facts and explicit, snapshot-bound human review."""

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from statistics import mean


def fingerprint(result):
    payload = {
        k: result.get(k) for k in ("sha256", "tables", "issues", "pages", "edits")
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def assessment(result):
    tables = result["tables"]
    issues = result["issues"]
    pages = result["pages"]
    rows = [row for t in tables for row in t["rows"]]
    ocr = [r for r in rows if r["method"].startswith("OCR")]
    evidence = sum(
        all(
            len(part.get("bbox", [])) == 4
            and part.get("page") in range(1, result["page_count"] + 1)
            for part in r.get("sources", [r])
        )
        for r in rows
    )
    reviewed = result.get("review", {}).get("status") == "reviewed" and result[
        "review"
    ].get("fingerprint") == fingerprint(result)
    counts = Counter(i["severity"] for i in issues)
    return {
        "pages_extracted": sum(p["status"] == "extracted" for p in pages),
        "pages_total": result["page_count"],
        "pages_needing_review": [
            p["page"] for p in pages if p["status"] != "extracted"
        ],
        "rows": len(rows),
        "tables": len(tables),
        "max_columns": max((len(t["headers"]) for t in tables), default=0),
        "errors": counts["error"],
        "warnings": counts["warning"],
        "findings": len(issues),
        "flagged_rows": len({(i["table"], i["row"]) for i in issues if i.get("row")}),
        "rows_with_evidence": evidence,
        "ocr_rows": len(ocr),
        "ocr_recognition_mean": round(mean(r["confidence"] for r in ocr), 4)
        if ocr
        else None,
        "ocr_low_score_rows": sum(
            r["confidence"] < 0.88
            or any(c is not None and c < 0.88 for c in r.get("cell_confidence", []))
            for r in ocr
        ),
        "source_parts": sum(len(r.get("sources", [r])) for r in rows),
        "continued_rows": sum(bool(r.get("continued_across_pages")) for r in rows),
        "merged_value_rows": sum(
            bool(r.get("inherited_cells") or r.get("merged_cells")) for r in rows
        ),
        "issue_types": dict(Counter(i["kind"] for i in issues)),
        "review_status": "reviewed" if reviewed else "pending",
        "can_review": bool(rows) and evidence == len(rows),
        "export_label": "Reviewed" if reviewed else "Draft — review pending",
    }


def enrich(result):
    result.setdefault("review", {"status": "pending"})
    result.setdefault("review_history", [])
    result["quality"] = assessment(result)
    return result


def revoke(result, reason):
    if result.get("review", {}).get("status") == "reviewed":
        result.setdefault("review_history", []).append(
            {
                **result["review"],
                "invalidated_at": datetime.now(timezone.utc).isoformat(),
                "reason": reason,
            }
        )
    result["review"] = {"status": "pending", "reason": reason}
    return enrich(result)


def approve(result, note="", accept_findings=False):
    q = assessment(result)
    if not q["can_review"]:
        raise ValueError(
            "A result with data rows and complete row evidence is required."
        )
    if q["findings"] and (not accept_findings or not note.strip()):
        raise ValueError(
            "Review the outstanding findings, acknowledge them and record a review note."
        )
    result["review"] = {
        "status": "reviewed",
        "at": datetime.now(timezone.utc).isoformat(),
        "note": note.strip(),
        "accepted_findings": q["findings"],
        "fingerprint": fingerprint(result),
    }
    return enrich(result)
