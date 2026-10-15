"""Reproducible external-fixture check; download only with an explicit --fetch."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.engine import extract, clean


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Download pinned public PDF fixtures to ignored tmp/public-data",
    )
    parser.add_argument("--label", default="final")
    args = parser.parse_args()
    manifest = json.loads(
        (ROOT / "evaluation/public/manifest.json").read_text(encoding="utf-8")
    )
    cache = ROOT / "tmp/public-data"
    cache.mkdir(parents=True, exist_ok=True)
    results = []
    for case in manifest["cases"]:
        path = cache / case["file"]
        if args.fetch:
            data = urlopen(case["url"], timeout=45).read()
            if hashlib.sha256(data).hexdigest() != case["sha256"]:
                raise ValueError("Source hash mismatch: " + case["file"])
            path.write_bytes(data)
        if not path.exists():
            raise SystemExit(
                "Run python scripts/public_evaluation.py --fetch once to obtain the public fixtures."
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != case["sha256"]:
            raise ValueError("Source hash mismatch: " + case["file"])
        result = extract(path)
        actual = []
        for table in result["tables"]:
            for row in table["rows"]:
                cells = list(row["cells"])
                if case["comparison_mode"] == "anchor_cells":
                    for inherited in row.get("inherited_cells", []):
                        cells[inherited["column"] - 1] = ""
                actual.append(cells)
        expected = case["rows"]
        correct = sum(
            clean(v) == clean(actual[ri][ci])
            for ri, row in enumerate(expected)
            for ci, v in enumerate(row)
            if ri < len(actual) and ci < len(actual[ri])
        )
        denominator = max(sum(map(len, expected)), sum(map(len, actual)))
        headers = (
            len(result["tables"]) == 1
            and result["tables"][0]["headers"] == case["headers"]
        )
        entry = {
            "file": case["file"],
            "expected_rows": len(expected),
            "actual_rows": len(actual),
            "correct_cells": correct,
            "denominator": denominator,
            "cell_accuracy": round(correct / denominator, 6) if denominator else 1,
            "headers_exact": headers,
            "exact": actual == expected and headers,
            "comparison_mode": case["comparison_mode"],
            "findings": dict(Counter(i["kind"] for i in result["issues"])),
            "seconds": result["elapsed_seconds"],
        }
        results.append(entry)
        print(entry, flush=True)
        (cache / (case["file"] + ".result.json")).write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "scope": manifest["scope"],
        "source_commit": manifest["commit"],
        "results": results,
    }
    (ROOT / "reports" / f"public-evaluation-{args.label}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return 0 if all(r["exact"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
