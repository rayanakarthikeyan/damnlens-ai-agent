"""Reproducible extraction evaluation; no self-reported model accuracy."""

import json
import platform
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))
from app.engine import clean, extract  # noqa: E402 - direct script entry point
from app.exporter import xlsx  # noqa: E402 - direct script entry point


def benchmark():
    truth = json.loads((ROOT / "samples" / "ground_truth.json").read_text())
    output = ROOT / "reports"
    output.mkdir(exist_ok=True)
    (ROOT / "samples" / "converted").mkdir(exist_ok=True)
    results = []
    for filename, expected in truth.items():
        print("Extracting", filename, flush=True)
        r = extract(
            ROOT / "samples" / filename,
            lambda d, t, m: print(f"  {d}/{t} {m}", flush=True),
        )
        (
            ROOT / "samples" / "converted" / filename.replace(".pdf", ".xlsx")
        ).write_bytes(xlsx(r))
        (output / filename.replace(".pdf", ".json")).write_text(
            json.dumps(r, indent=2), encoding="utf-8"
        )
        actual = [row["cells"] for table in r["tables"] for row in table["rows"]]
        exp = expected["rows"]
        width = len(expected["headers"])
        expected_cells = len(exp) * width
        correct = sum(
            clean(c) == clean(actual[ri][ci])
            for ri, row in enumerate(exp)
            for ci, c in enumerate(row)
            if ri < len(actual) and ci < len(actual[ri])
        )
        denominator = max(expected_cells, sum(len(row) for row in actual))
        matches = sum(
            (
                Counter(tuple(clean(c) for c in row) for row in exp)
                & Counter(tuple(clean(c) for c in row) for row in actual)
            ).values()
        )
        headers_correct = (
            bool(r["tables"]) and r["tables"][0]["headers"] == expected["headers"]
        )
        results.append(
            {
                "file": filename,
                "pages": r["page_count"],
                "expected_rows": len(exp),
                "actual_rows": len(actual),
                "expected_cells": expected_cells,
                "actual_cells": sum(map(len, actual)),
                "correct_cells": correct,
                "cell_accuracy": round(correct / denominator, 6),
                "row_recall": round(matches / len(exp), 6),
                "row_precision": round(matches / len(actual), 6) if actual else 0,
                "headers_exact": headers_correct,
                "seconds": r["elapsed_seconds"],
                "findings": len(r["issues"]),
                "finding_types": dict(Counter(i["kind"] for i in r["issues"])),
            }
        )
        print(results[-1], flush=True)
    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "environment": platform.platform(),
        "methodology": "Compare normalized whitespace in every output cell to independently generated source ground truth in original row order. Cell accuracy divides matching cells by the larger of expected and actual cell counts, penalizing dropped and extra cells. Row recall and precision use exact full-row multiset matches, preserving duplicate multiplicity. Header equality is reported separately. Source errors count as correct only when faithfully preserved.",
        "limitations": "Only three original, English, synthetic fixtures; clean scans at 150 DPI and consistent layouts. Results do not establish accuracy on unseen PDFs, handwriting, merged cells, nested tables, complex borderless layouts or other languages. No hidden evaluation was performed.",
        "results": results,
    }
    (output / "benchmark.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    lines = [
        "# Accuracy and validation report",
        "",
        f"Generated: {report['generated']}",
        "",
        report["methodology"],
        "",
        "| Fixture | Pages | Matching cells | Cell accuracy | Exact row recall | Headers | Seconds |",
        "|---|---:|---:|---:|---:|---|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r['file']} | {r['pages']} | {r['correct_cells']}/{r['expected_cells']} | {r['cell_accuracy']:.2%} | {r['row_recall']:.2%} | {r['headers_exact']} | {r['seconds']} |"
        )
    lines += ["", "## Validation findings", ""]
    for r in results:
        lines.append(
            f"- **{r['file']}:** {r['findings']} findings: {json.dumps(r['finding_types'])}."
        )
    lines += [
        "",
        "## Practical limits",
        "",
        report["limitations"],
        "",
        "Confidence scores from OCR are recognition confidence only, never measured accuracy. Native extraction uses 1.0 as a non-OCR marker, not an accuracy estimate. Human review remains necessary.",
        "",
        "## Reproduce",
        "",
        "`python scripts/generate_samples.py` then `python scripts/benchmark.py`. Test additional adversarial and boundary cases with `python -m pytest -q`.",
        "",
        "Synthetic fixtures were authored for this project with ReportLab; scans were rasterized with PyMuPDF. These metrics are transparent development checks, not a claim of independent third-party evaluation.",
    ]
    (output / "ACCURACY_REPORT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    benchmark()
