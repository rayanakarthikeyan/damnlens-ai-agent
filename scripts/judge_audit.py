"""Varied synthetic development audit. Failures are measured, never hidden."""

import argparse
import io
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageEnhance, ImageFilter
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engine import clean, extract  # noqa: E402 - direct script entry point

HEADERS = [
    "Item ID",
    "Description",
    "Quantity",
    "Unit price",
    "Net",
    "Tax",
    "Total",
    "Region",
    "Status",
    "Category",
    "Reference",
    "Currency",
]
ROWS = [
    [
        f"P{i:03}",
        f"Part {i}",
        str(i),
        "20.00",
        f"{i * 20:.2f}",
        f"{i * 2:.2f}",
        f"{i * 22:.2f}",
        "South",
        "Paid",
        "Office",
        f"REF-{i:03}",
        "USD",
    ]
    for i in range(1, 9)
]
WIDTHS = [64, 112, 65, 75, 75, 65, 75, 65, 65, 74, 92, 70]


def digital(borderless=False, merged=False):
    """Different typography, spacing and page design from the submission samples."""
    stream = io.BytesIO()
    c = canvas.Canvas(stream, pagesize=(1000, 660))
    c.setFont("Times-Bold", 21)
    c.drawString(36, 610, "Quarterly procurement ledger")
    c.setFont("Times-Roman", 11)
    c.drawString(36, 586, "Fictional records for development evaluation")
    top = 543
    if merged:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, top - 15, "Procurement details")
        c.drawString(36 + sum(WIDTHS[:4]) + 4, top - 15, "Amounts and classification")
        c.rect(36, top - 24, sum(WIDTHS), 24)
        top -= 24
    for ri, row in enumerate([HEADERS] + ROWS):
        x = 36
        for ci, (value, width) in enumerate(zip(row, WIDTHS, strict=False)):
            c.setFont("Helvetica-Bold" if ri == 0 else "Helvetica", 10)
            if ri > 0 and 2 <= ci <= 6:
                c.drawRightString(x + width - 5, top - ri * 27 - 18, value)
            else:
                c.drawString(x + 5, top - ri * 27 - 18, value)
            x += width
    if not borderless:
        c.setLineWidth(0.6)
        x = 36
        for width in [0] + WIDTHS:
            x += width
            c.line(x, top, x, top - 9 * 27)
        for r in range(10):
            c.line(36, top - r * 27, 36 + sum(WIDTHS), top - r * 27)
    c.setFont("Times-Italic", 10)
    c.drawString(
        36, 65, "Prepared for a public synthetic evaluation. No personal information."
    )
    c.save()
    return stream.getvalue()


def raster(data, rotation=0, skew=0, degraded=False):
    with fitz.open("pdf", data) as source:
        png = source[0].get_pixmap(dpi=150, alpha=False).tobytes("png")
    image = Image.open(io.BytesIO(png)).convert("RGB")
    if degraded:
        image = (
            ImageEnhance.Contrast(image)
            .enhance(0.55)
            .filter(ImageFilter.GaussianBlur(0.35))
        )
    if rotation:
        image = image.rotate(rotation, expand=True, fillcolor="white")
    if skew:
        image = image.rotate(skew, expand=False, fillcolor="white")
    png = io.BytesIO()
    image.save(png, format="PNG")
    dest = fitz.open()
    dest.new_page(width=image.width * 0.48, height=image.height * 0.48).insert_image(
        fitz.Rect(0, 0, image.width * 0.48, image.height * 0.48), stream=png.getvalue()
    )
    result = dest.tobytes(deflate=True)
    dest.close()
    return result


def cases():
    standard = digital()
    yield "right_aligned_native", standard, ROWS, HEADERS
    yield "borderless_native", digital(borderless=True), ROWS, HEADERS
    yield "merged_group_header", digital(merged=True), ROWS, HEADERS
    for angle in (90, 180, 270):
        with fitz.open("pdf", standard) as document:
            document[0].set_rotation(angle)
            yield f"pdf_rotation_{angle}", document.tobytes(), ROWS, HEADERS
    yield "scan_clean", raster(standard), ROWS, HEADERS
    yield "scan_borderless", raster(digital(borderless=True)), ROWS, HEADERS
    yield "scan_skew_2deg", raster(standard, skew=2), ROWS, HEADERS
    yield "scan_degraded", raster(standard, degraded=True), ROWS, HEADERS
    for angle in (90, 180, 270):
        yield f"scan_sideways_{angle}", raster(standard, rotation=angle), ROWS, HEADERS
    with fitz.open("pdf", standard) as document:
        with fitz.open("pdf", raster(standard)) as scan:
            document.insert_pdf(scan)
        yield "mixed_native_scan", document.tobytes(), ROWS * 2, HEADERS
    stream = io.BytesIO()
    c = canvas.Canvas(stream)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(40, 780, "Quarterly narrative report")
    c.setFont("Helvetica", 12)
    for i, line in enumerate(
        [
            "The department reviewed operational costs and regional performance.",
            "Revenue remained stable while the office relocated to a new building.",
            "The next review will consider procurement and supplier agreements.",
            "This document contains paragraphs rather than any tabular data.",
            "No transaction records or numeric columns are presented here.",
        ]
    ):
        c.drawString(40, 740 - i * 23, line)
    c.save()
    yield "narrative_no_table", stream.getvalue(), [], []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="after")
    parser.add_argument(
        "--case", action="append", help="Optional case name; default is all"
    )
    args = parser.parse_args()
    output = ROOT / "evaluation"
    (output / "pdfs").mkdir(parents=True, exist_ok=True)
    results = []
    audit_cases = list(cases())
    (output / "ground_truth.json").write_text(
        json.dumps(
            {
                f"{name}.pdf": {"headers": headers, "rows": expected}
                for name, _, expected, headers in audit_cases
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    for name, data, expected, headers in audit_cases:
        if args.case and name not in args.case:
            continue
        path = output / "pdfs" / f"{name}.pdf"
        path.write_bytes(data)
        print("Evaluating", name, flush=True)
        result = extract(path)
        actual = [r["cells"] for t in result["tables"] for r in t["rows"]]
        correct = sum(
            clean(cell) == clean(actual[ri][ci])
            for ri, row in enumerate(expected)
            for ci, cell in enumerate(row)
            if ri < len(actual) and ci < len(actual[ri])
        )
        denominator = max(len(expected) * len(headers), sum(map(len, actual)))
        matches = sum(
            (Counter(map(tuple, expected)) & Counter(map(tuple, actual))).values()
        )
        header_match = (
            not result["tables"]
            if not headers
            else bool(result["tables"])
            and all(t["headers"] == headers for t in result["tables"])
        )
        entry = {
            "case": name,
            "expected_rows": len(expected),
            "actual_rows": len(actual),
            "tables": len(result["tables"]),
            "correct_cells": correct,
            "denominator": denominator,
            "cell_accuracy": round(correct / denominator, 6) if denominator else 1.0,
            "exact_rows": matches,
            "headers_exact": header_match,
            "passed": actual == expected
            and header_match
            and (len(result["tables"]) == 1 if expected else not result["tables"]),
            "findings": dict(Counter(i["kind"] for i in result["issues"])),
            "seconds": result["elapsed_seconds"],
        }
        results.append(entry)
        (output / f"{name}-result.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        print(entry, flush=True)
    report = {
        "application": "DamnLens AI Agent",
        "generated": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "scope": "15 varied English synthetic development cases with 12 columns. Includes three right-angle PDF rotations, three physical scan rotations, borderless, grouped headers, 2-degree skew, reduced contrast, a mixed document and prose. These are development regressions after fixes, not an independent hidden set. Headers and exact data-row order are checked separately. Extra/missing cells are penalized. No-table cases pass only with no fabricated tables.",
        "results": results,
    }
    (ROOT / "reports" / f"judge-audit-{args.label}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(
        f"{sum(r['passed'] for r in results)}/{len(results)} exact cases passed",
        flush=True,
    )
    return 0 if results and all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
