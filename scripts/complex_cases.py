"""Original challenge fixtures with explicit ground truth, unrelated to the OCR code."""

import io

from reportlab.pdfgen import canvas

from scripts.judge_audit import raster

WIDTHS = [75, 145, 65, 75, 75, 65, 75, 72, 72, 72, 90, 70]
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
        f"Z{i:03}",
        f"Precision part {i}",
        str(i + 1),
        "30.00",
        f"{(i + 1) * 30:.2f}",
        f"{(i + 1) * 3:.2f}",
        f"{(i + 1) * 33:.2f}",
        "North",
        "Open",
        "Tools",
        f"B-{i:03}",
        "USD",
    ]
    for i in range(1, 7)
]


def draw(
    c,
    rows,
    headers=HEADERS,
    *,
    top=600,
    multiline=False,
    groups=False,
    row_merge=False,
    borderless=False,
    account=None,
):
    left = 35
    if account:
        c.setFont("Helvetica-Bold", 12)
        c.drawString(left, top + 22, f"Account number: {account}")
    x = [left]
    for width in WIDTHS[: len(headers)]:
        x.append(x[-1] + width)
    height = 42 if multiline else 28
    if groups:
        c.setFont("Helvetica-Bold", 11)
        for start, end, title in [
            (0, 2, "Item details"),
            (2, 7, "Amount summary"),
            (7, 12, "Classification"),
        ]:
            c.rect(x[start], top, x[end] - x[start], 26)
            c.drawString(x[start] + 5, top + 8, title)
    c.setFont("Helvetica-Bold", 10)
    for col, value in enumerate(headers):
        lines = (
            value.split(" ")
            if multiline and value in {"Item ID", "Unit price"}
            else [value]
        )
        for li, text in enumerate(lines):
            c.drawString(x[col] + 5, top - 16 - li * 13, text)
    for r, row in enumerate(rows):
        c.setFont("Helvetica", 10)
        for col, value in enumerate(row):
            if row_merge and col == 7 and r == 1:
                continue
            text = value
            for li, line in enumerate(text.split("\n")):
                c.drawString(x[col] + 5, top - height - r * 38 - 16 - li * 13, line)
    bottom = top - height - len(rows) * 38
    if not borderless:
        c.setLineWidth(0.7)
        for xx in x:
            c.line(xx, top, xx, bottom)
        c.line(left, top, x[-1], top)
        for ri in range(len(rows) + 1):
            y = top - height - ri * 38
            if row_merge and ri == 1:
                c.line(left, y, x[7], y)
                c.line(x[8], y, x[-1], y)
            else:
                c.line(left, y, x[-1], y)
    return bottom


def document(pages):
    stream = io.BytesIO()
    c = canvas.Canvas(stream, pagesize=(1100, 750))
    for options in pages:
        c.setFont("Times-Bold", 22)
        c.drawString(35, 710, "DamnLens complex-table development fixture")
        draw(c, **options)
        c.showPage()
    c.save()
    return stream.getvalue()


def cases():
    def one(name, data, rows=ROWS, headers=HEADERS, **expect):
        return name, data, {"tables": [{"headers": headers, "rows": rows}], **expect}

    yield one("multiline_grid_header", document([{"rows": ROWS, "multiline": True}]))
    yield one(
        "grouped_header_with_keywords",
        document([{"rows": ROWS, "groups": True}]),
        header_context=True,
    )
    wrapped = [r.copy() for r in ROWS]
    wrapped[2][1] = "Precision part 3\nwith mounting kit"
    truth = [r.copy() for r in wrapped]
    truth[2][1] = "Precision part 3 with mounting kit"
    yield one("wrapped_grid_cell", document([{"rows": wrapped}]), truth)
    merged = [r.copy() for r in ROWS]
    merged[1][7] = merged[0][7]
    yield one(
        "vertical_merged_region",
        document([{"rows": merged, "row_merge": True}]),
        merged,
        merged_cells=True,
    )
    yield one(
        "borderless_multiline_header",
        document([{"rows": ROWS, "multiline": True, "borderless": True}]),
    )
    # Two physical rows form a single record, crossing a repeated page header.
    split = [r.copy() for r in ROWS]
    split[2][1] = "Precision part 3 with mounting kit"
    continuation = [""] * 12
    continuation[1] = "with mounting kit"
    yield one(
        "row_split_across_pages",
        document([{"rows": ROWS[:3]}, {"rows": [continuation] + ROWS[3:]}]),
        split,
        split_row=True,
    )
    yield (
        "distinct_accounts_same_schema",
        document(
            [
                {"rows": ROWS[:3], "account": "DUMMY-A"},
                {"rows": ROWS[3:], "account": "DUMMY-B"},
            ]
        ),
        {
            "tables": [
                {"headers": HEADERS, "rows": ROWS[:3]},
                {"headers": HEADERS, "rows": ROWS[3:]},
            ]
        },
    )
    # Adjacent repeated labels require the year group for an unambiguous schema.
    stream = io.BytesIO()
    c = canvas.Canvas(stream, pagesize=(500, 500))
    xs = [35, 140, 245, 350, 455]
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, 412, "2025")
    c.drawString(250, 412, "2026")
    c.line(35, 430, 455, 430)
    c.line(35, 402, 455, 402)
    for xx in (35, 245, 455):
        c.line(xx, 430, xx, 402)
    for xx in xs:
        c.line(xx, 402, xx, 314)
    for yy in (374, 344, 314):
        c.line(35, yy, 455, yy)
    for i, label in enumerate(["Sales", "Cost", "Sales", "Cost"]):
        c.drawString(xs[i] + 5, 384, label)
    c.setFont("Helvetica", 11)
    for ri, row in enumerate([["120", "70", "180", "95"], ["90", "40", "130", "65"]]):
        for ci, value in enumerate(row):
            c.drawString(xs[ci] + 5, 354 - ri * 30, value)
    c.save()
    yield (
        "hierarchical_duplicate_headers",
        stream.getvalue(),
        {
            "tables": [
                {
                    "headers": ["2025 Sales", "2025 Cost", "2026 Sales", "2026 Cost"],
                    "rows": [["120", "70", "180", "95"], ["90", "40", "130", "65"]],
                }
            ],
            "header_context": True,
        },
    )
    # These scans vary layout, not only the numbers in the existing clean fixture.
    yield one(
        "scan_grouped_header",
        raster(document([{"rows": ROWS, "groups": True}])),
        header_context=True,
    )
    yield one(
        "scan_multiline_header", raster(document([{"rows": ROWS, "multiline": True}]))
    )
    yield one(
        "scan_borderless_multiline",
        raster(document([{"rows": ROWS, "multiline": True, "borderless": True}])),
    )
    yield one("scan_low_contrast", raster(document([{"rows": ROWS}]), degraded=True))


def additional_cases():
    blank = [r.copy() for r in ROWS]
    blank[1][7] = ""
    expected = {"tables": [{"headers": HEADERS, "rows": blank}]}
    yield "intentional_blank_native", document([{"rows": blank}]), expected
    yield "intentional_blank_scan", raster(document([{"rows": blank}])), expected
    nested = io.BytesIO()
    c = canvas.Canvas(nested, pagesize=(600, 550))
    for x in (35, 175, 415, 545):
        c.line(x, 420, x, 280)
    c.line(35, 460, 545, 460)
    c.line(35, 420, 545, 420)
    c.line(175, 390, 545, 390)
    for x in (35, 175, 545):
        c.line(x, 460, x, 420)
    for y in (350, 315):
        c.line(175, y, 545, y)
    c.line(35, 280, 545, 280)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, 440, "Order ID")
    c.drawString(180, 440, "Line items")
    c.drawString(180, 403, "Product")
    c.drawString(420, 403, "Quantity")
    c.setFont("Helvetica", 12)
    c.drawString(40, 370, "A42")
    for y, name, qty in [
        (370, "Cable", "2"),
        (333, "Plug", "4"),
        (297, "Adapter", "1"),
    ]:
        c.drawString(180, y, name)
        c.drawString(420, y, qty)
    c.save()
    expected = {
        "tables": [
            {
                "headers": ["Order ID", "Product", "Quantity"],
                "rows": [
                    ["A42", "Cable", "2"],
                    ["A42", "Plug", "4"],
                    ["A42", "Adapter", "1"],
                ],
            }
        ],
        "header_context": True,
    }
    yield "nested_line_items", nested.getvalue(), expected
    yield "scan_nested_line_items", raster(nested.getvalue()), expected


def write_cases(root):
    import json

    (root / "pdfs").mkdir(parents=True, exist_ok=True)
    truth = {}
    for name, data, expected in list(cases()) + list(additional_cases()):
        (root / "pdfs" / f"{name}.pdf").write_bytes(data)
        truth[name] = expected
    (root / "ground_truth.json").write_text(
        json.dumps(truth, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    from pathlib import Path

    write_cases(Path(__file__).resolve().parents[1] / "evaluation/complex")
