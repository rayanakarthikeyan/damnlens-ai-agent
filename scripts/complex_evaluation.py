"""Measure complex-table reconstruction against explicit source ground truth."""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))
from app.engine import clean, extract  # noqa: E402 - direct script entry point
from app.exporter import xlsx  # noqa: E402 - direct script entry point


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Regenerate the original dummy PDFs and ground truth first",
    )
    args = parser.parse_args()
    base = ROOT / "evaluation/complex"
    if args.generate:
        from scripts.complex_cases import write_cases

        write_cases(base)
    truth = json.loads((base / "ground_truth.json").read_text(encoding="utf-8"))
    (base / "results").mkdir(exist_ok=True)
    (base / "converted").mkdir(exist_ok=True)
    measurements = []
    for name, expected in truth.items():
        print("Extracting", name, flush=True)
        result = extract(base / "pdfs" / f"{name}.pdf")
        actual = [
            {"headers": t["headers"], "rows": [r["cells"] for r in t["rows"]]}
            for t in result["tables"]
        ]
        exp_rows = [r for t in expected["tables"] for r in t["rows"]]
        act_rows = [r for t in actual for r in t["rows"]]
        correct = sum(
            clean(v) == clean(act_rows[ri][ci])
            for ri, row in enumerate(exp_rows)
            for ci, v in enumerate(row)
            if ri < len(act_rows) and ci < len(act_rows[ri])
        )
        denominator = max(sum(map(len, exp_rows)), sum(map(len, act_rows)))
        entry = {
            "case": name,
            "expected_tables": len(expected["tables"]),
            "actual_tables": len(actual),
            "expected_rows": len(exp_rows),
            "actual_rows": len(act_rows),
            "correct_cells": correct,
            "denominator": denominator,
            "cell_accuracy": round(correct / denominator, 6) if denominator else 1,
            "headers_exact": len(actual) == len(expected["tables"])
            and all(
                a["headers"] == b["headers"]
                for a, b in zip(actual, expected["tables"], strict=False)
            ),
            "exact": actual == expected["tables"],
            "findings": dict(Counter(i["kind"] for i in result["issues"])),
            "seconds": result["elapsed_seconds"],
        }
        if expected.get("header_context"):
            entry["exact"] &= bool(result["tables"][0].get("header_paths"))
        if expected.get("split_row"):
            entry["exact"] &= (
                len(result["tables"][0]["rows"][2].get("sources", [])) == 2
            )
        measurements.append(entry)
        print(entry, flush=True)
        (base / "results" / f"{name}.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        (base / "converted" / f"{name}.xlsx").write_bytes(xlsx(result))
    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "scope": "16 original English development fixtures: multi-line and hierarchical headers, actual vertical merges, nested line items, cross-page row parts, distinct account contexts, right-aligned borderless tables and deliberate blank cells. All cells, table counts and ordered headers must match. These cases were used to repair the engine and are regression evidence, not an independent hidden corpus. OCR scores are not measured accuracy. Shared values and recovered cells remain flagged for source review.",
        "results": measurements,
    }
    (ROOT / "reports/complex-evaluation.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(
        f"{sum(r['exact'] for r in measurements)}/{len(measurements)} exact cases; {sum(r['correct_cells'] for r in measurements)}/{sum(r['denominator'] for r in measurements)} cells",
        flush=True,
    )
    return 0 if all(r["exact"] for r in measurements) else 1


if __name__ == "__main__":
    raise SystemExit(main())
