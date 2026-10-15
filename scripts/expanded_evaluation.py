"""Source-frozen public layout checkpoints; partial audits are labelled explicitly."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import re
import sys
from urllib.request import urlopen

import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.engine import clean, extract


def compare_table(actual, expected):
    rows = [r["cells"] for r in actual["rows"]]
    checks, failures = [], []

    def check(condition, detail):
        checks.append(bool(condition))
        if not condition:
            failures.append(detail)

    check(
        len(actual["headers"]) == expected["columns"],
        f"columns {len(actual['headers'])} != {expected['columns']}",
    )
    if expected["headers"] is not None:
        check(actual["headers"] == expected["headers"], f"headers {actual['headers']}")
    if "selected_rows" in expected:
        for target in expected["selected_rows"]:
            found = [
                r for r in rows if clean(re.sub(r"\.{3,}", "", r[0])) == target["key"]
            ]
            check(
                len(found) == 1, f"selected row {target['key']}: {len(found)} matches"
            )
            for col, value in enumerate(target["values"], 1):
                actual_value = (
                    found[0][col] if len(found) == 1 and col < len(found[0]) else None
                )
                check(
                    actual_value == value,
                    f"{target['key']} col {col + 1}: {actual_value!r} != {value!r}",
                )
    else:
        check(
            len(rows) == len(expected["rows"]),
            f"rows {len(rows)} != {len(expected['rows'])}",
        )
        columns = expected.get("checked_columns", list(range(expected["columns"])))
        for ri, row in enumerate(expected["rows"]):
            for ei, ci in enumerate(columns):
                value = rows[ri][ci] if ri < len(rows) and ci < len(rows[ri]) else None
                check(
                    clean(value) == clean(row[ei]),
                    f"row {ri + 1} col {ci + 1}: {value!r} != {row[ei]!r}",
                )
    return checks, failures


def evaluate(result, expected):
    actual = result["tables"]
    possibilities = itertools.permutations(
        range(len(actual)), min(len(actual), len(expected))
    )
    candidates = []
    for indices in possibilities:
        checks = [len(actual) == len(expected)]
        failures = [] if checks[0] else [f"tables {len(actual)} != {len(expected)}"]
        for i, target in enumerate(expected):
            if i >= len(indices):
                checks.append(False)
                failures.append(f"Missing table {i + 1}")
            else:
                good, errors = compare_table(actual[indices[i]], target)
                checks.extend(good)
                failures.extend(errors)
        candidates.append((checks, failures))
    if not candidates:
        return [False], ["No extracted tables"]
    return max(candidates, key=lambda entry: sum(entry[0]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--label", default="after")
    parser.add_argument("--case", action="append")
    parser.add_argument(
        "--check-review-routing",
        action="store_true",
        help="Accept only a sole header-text mismatch with a recorded OCR disagreement; all other checkpoint failures still fail.",
    )
    args = parser.parse_args()
    output = ROOT / "reports" / f"expanded-{args.label}.json"
    if args.label == "before" and output.exists():
        raise SystemExit(
            "The first-pass baseline already exists; use a different label."
        )
    manifest_path = ROOT / "evaluation/expanded/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cache = ROOT / "tmp/unseen-public"
    cache.mkdir(parents=True, exist_ok=True)
    measurements = []
    for case in manifest["cases"]:
        if args.case and case["id"] not in args.case:
            continue
        source = cache / case["file"]
        if not source.exists() and args.fetch:
            source.write_bytes(urlopen(case["url"], timeout=45).read())
        if not source.exists():
            raise SystemExit("Fetch public fixtures once using --fetch.")
        if hashlib.sha256(source.read_bytes()).hexdigest() != case["sha256"]:
            raise ValueError("Source checksum mismatch: " + case["file"])
        path = source
        if case["variant"] == "scan":
            path = cache / f"{case['id']}.pdf"
            with fitz.open(source) as original, fitz.open() as scanned:
                for page in original:
                    pix = page.get_pixmap(dpi=case["dpi"], alpha=False)
                    target = scanned.new_page(
                        width=page.rect.width, height=page.rect.height
                    )
                    target.insert_image(target.rect, stream=pix.tobytes("png"))
                scanned.save(path)
            with fitz.open(path) as doc:
                assert all(not page.get_text().strip() for page in doc)
        print("Evaluating", case["id"], flush=True)
        try:
            result = extract(path)
            checks, failures = evaluate(result, case["tables"])
            (cache / f"{case['id']}-{args.label}.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
            entry = {
                "case": case["id"],
                "passed": all(checks),
                "checks_passed": sum(checks),
                "checks": len(checks),
                "failures": failures,
                "tables": [
                    {"columns": len(t["headers"]), "rows": len(t["rows"])}
                    for t in result["tables"]
                ],
                "seconds": result["elapsed_seconds"],
                "findings": dict(Counter(i["kind"] for i in result["issues"])),
                "ocr_disagreements": sum(
                    len(t.get("header_ocr_disagreements", []))
                    + sum(len(r.get("ocr_disagreements", [])) for r in t["rows"])
                    for t in result["tables"]
                ),
            }
        except Exception as exc:
            entry = {
                "case": case["id"],
                "passed": False,
                "checks_passed": 0,
                "checks": 1,
                "failures": [str(exc)],
            }
        measurements.append(entry)
        print({**entry, "failures": entry["failures"][:5]}, flush=True)
    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "engine_sha256": hashlib.sha256(
            (ROOT / "app/engine.py").read_bytes()
        ).hexdigest(),
        "scope": manifest["scope"],
        "comparison": "Whole-table shape and ordered selected source-cell checkpoints; dotted leaders removed only for selected row-label matching. Partial checks are NOT whole-document cell accuracy. Table assignment is one-to-one; extra/missing tables fail.",
        "results": measurements,
    }
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"{sum(r['passed'] for r in measurements)}/{len(measurements)} exact checkpoint cases",
        flush=True,
    )
    accepted_review = (
        lambda r: r["checks_passed"] == r["checks"] - 1
        and r.get("ocr_disagreements", 0) > 0
        and len(r["failures"]) == 1
        and r["failures"][0].startswith("headers ")
    )
    if args.check_review_routing:
        review_cases = [
            r for r in measurements if not r["passed"] and accepted_review(r)
        ]
        print(
            f"Review routing: {len(review_cases)} header-only residuals flagged; strict extraction counts above remain unchanged.",
            flush=True,
        )
        return (
            0
            if measurements
            and all(r["passed"] or accepted_review(r) for r in measurements)
            else 1
        )
    return 0 if measurements and all(r["passed"] for r in measurements) else 1


if __name__ == "__main__":
    raise SystemExit(main())
