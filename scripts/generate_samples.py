"""Generate original public dummy fixtures and independent extraction ground truth."""

import io
import json
import sys
from pathlib import Path

import pymupdf as fitz
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 1120, 700


def render_pdf(path, title, headers, pages, widths, scanned=False, borderless=False):
    stream = io.BytesIO()
    c = canvas.Canvas(stream, pagesize=(WIDTH, HEIGHT))
    for pi, rows in enumerate(pages):
        c.setFillColor(HexColor("#173c37"))
        c.rect(0, HEIGHT - 9, WIDTH, 9, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(44, HEIGHT - 44, "LEDGERLENS / DEMO DOCUMENTS")
        c.setFont("Helvetica", 8)
        c.setFillColor(HexColor("#8a9980"))
        c.drawRightString(
            WIDTH - 44, HEIGHT - 44, "PUBLIC DUMMY DATA - NO PERSONAL INFORMATION"
        )
        c.setFillColor(HexColor("#243b37"))
        c.setFont("Helvetica-Bold", 25)
        c.drawString(44, HEIGHT - 88, title)
        c.setFont("Helvetica", 10)
        c.setFillColor(HexColor("#829078"))
        c.drawString(
            44,
            HEIGHT - 111,
            "Reporting period: October 2026    |    Currency: USD    |    Fictional business records",
        )
        x = 44
        top = HEIGHT - 147
        row_height = 28
        c.setFillColor(HexColor("#eaf2e1"))
        c.rect(x, top - row_height, sum(widths), row_height, fill=1, stroke=0)
        for ri, row in enumerate([headers] + rows):
            y = top - ri * row_height
            if ri > 0 and ri % 2 == 0:
                c.setFillColor(HexColor("#f7faf3"))
                c.rect(x, y - row_height, sum(widths), row_height, fill=1, stroke=0)
            c.setFillColor(HexColor("#263b30"))
            c.setFont(
                "Helvetica-Bold" if ri == 0 else "Helvetica", 10 if scanned else 9
            )
            xx = x
            for text, w in zip(row, widths):
                c.drawString(xx + 7, y - 18, str(text))
                xx += w
        if not borderless:
            c.setStrokeColor(HexColor("#9aab91"))
            c.setLineWidth(0.65)
            for ri in range(len(rows) + 2):
                y = top - ri * row_height
                c.line(x, y, x + sum(widths), y)
            xx = x
            for w in [0] + widths:
                xx += w
                c.line(xx, top, xx, top - (len(rows) + 1) * row_height)
        c.setFont("Helvetica", 8)
        c.setFillColor(HexColor("#9aa58e"))
        c.drawString(
            44,
            35,
            "Synthetic fixture. Values and errors are intentional; compare the exported workbook against this source.",
        )
        c.drawRightString(WIDTH - 44, 35, f"Page {pi + 1} of {len(pages)}")
        c.showPage()
    c.save()
    data = stream.getvalue()
    if scanned:
        # Strip all text and vector content: this is a genuine image-only PDF.
        src = fitz.open("pdf", data)
        dest = fitz.open()
        for page in src:
            png = page.get_pixmap(dpi=150, alpha=False).tobytes("png")
            dest.new_page(width=WIDTH, height=HEIGHT).insert_image(
                fitz.Rect(0, 0, WIDTH, HEIGHT), stream=png
            )
        data = dest.tobytes(deflate=True)
        dest.close()
        src.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def invoice_fixture(pages=3):
    headers = [
        "Item ID",
        "Date",
        "Description",
        "Region",
        "Quantity",
        "Unit price",
        "Tax %",
        "Net",
        "Tax",
        "Total",
        "Currency",
        "Status",
    ]
    rows = []
    for i in range(1, pages * 10 + 1):
        qty = i % 7 + 1
        price = 20 + i * 2
        net = qty * price
        tax = net * 0.1
        rows.append(
            [
                f"INV-{i:04d}",
                f"2026-10-{i % 28 + 1:02d}",
                f"Studio supply {i:02d}",
                ("East", "West", "North")[i % 3],
                str(qty),
                f"{price:.2f}",
                "10%",
                f"{net:.2f}",
                f"{tax:.2f}",
                f"{net + tax:.2f}",
                "USD",
                "Paid",
            ]
        )
    totals = [
        "TOTAL",
        "",
        "",
        "",
        str(sum(int(r[4]) for r in rows)),
        "",
        "",
        "%.2f" % sum(float(r[7]) for r in rows),
        "%.2f" % sum(float(r[8]) for r in rows),
        "%.2f" % sum(float(r[9]) for r in rows),
        "",
        "",
    ]
    chunks = [rows[i : i + 10] for i in range(0, len(rows), 10)]
    chunks[-1].append(totals)
    return headers, chunks, [88, 89, 136, 65, 72, 80, 55, 77, 75, 78, 72, 64]


def generate():
    samples = ROOT / "samples"
    truth = {}
    h, p, w = invoice_fixture()
    render_pdf(samples / "01_invoice_register.pdf", "Invoice register", h, p, w)
    truth["01_invoice_register.pdf"] = {
        "headers": h,
        "rows": sum(p, []),
        "pages": 3,
        "description": "Digital 12-column, three-page register with repeated headers and an aggregate total.",
    }
    h = [
        "SKU",
        "Date",
        "Description",
        "Location",
        "Quantity",
        "Unit price",
        "Tax %",
        "Net",
        "Tax",
        "Total",
        "Currency",
        "Status",
    ]
    p = []
    rows = []
    for i in range(1, 21):
        q = i + 2
        price = 15 + i
        net = q * price
        tax = net * 0.1
        rows.append(
            [
                f"SKU-{i:04d}",
                f"2026-10-{i:02d}",
                f"Office item {i:02d}",
                "Depot A",
                str(q),
                f"{price:.2f}",
                "10%",
                f"{net:.2f}",
                f"{tax:.2f}",
                f"{net + tax:.2f}",
                "USD",
                "Stock",
            ]
        )
    p = [rows[:10], rows[10:]]
    w = [88, 89, 136, 75, 72, 80, 55, 77, 75, 78, 72, 54]
    render_pdf(
        samples / "02_scanned_inventory.pdf",
        "Inventory reconciliation - scanned copy",
        h,
        p,
        w,
        scanned=True,
    )
    truth["02_scanned_inventory.pdf"] = {
        "headers": h,
        "rows": rows,
        "pages": 2,
        "description": "Image-only two-page, 12-column scan. No embedded text layer.",
    }
    h = [
        "Date",
        "Reference",
        "Description",
        "Channel",
        "Branch",
        "Debit",
        "Credit",
        "Balance",
        "Currency",
        "Category",
        "Status",
        "Notes",
    ]
    rows = []
    balance = 5000
    for i in range(1, 21):
        debit = 25 * i if i % 2 else 0
        credit = 0 if i % 2 else 80 * i
        balance = balance - debit + credit
        rows.append(
            [
                f"2026-10-{i:02d}",
                f"TXN-{i:04d}",
                f"Business entry {i:02d}",
                "Online",
                "Central",
                f"{debit:.2f}",
                f"{credit:.2f}",
                f"{balance:.2f}",
                "USD",
                "Operating",
                "Cleared",
                "Demo",
            ]
        )
    rows[5][5] = ""
    rows[8][7] = f"{float(rows[8][7]) + 75:.2f}"
    rows[11][8] = ""
    totals = [
        "TOTAL",
        "",
        "",
        "",
        "",
        "%.2f" % (sum(float(r[5] or 0) for r in rows) + 100),
        "%.2f" % sum(float(r[6]) for r in rows),
        "",
        "",
        "",
        "",
        "",
    ]
    p = [rows[:10], rows[10:] + [totals]]
    w = [89, 89, 136, 74, 74, 76, 76, 85, 72, 80, 70, 60]
    render_pdf(samples / "03_bank_statement.pdf", "Business account statement", h, p, w)
    truth["03_bank_statement.pdf"] = {
        "headers": h,
        "rows": sum(p, []),
        "pages": 2,
        "description": "A wrong debit total (+100), an altered balance (+75), a missing debit and missing currency. Source errors must be preserved and flagged.",
    }
    (samples / "ground_truth.json").write_text(
        json.dumps(truth, indent=2), encoding="utf-8"
    )
    print("Generated three original fixtures with ground truth.")


if __name__ == "__main__":
    generate()
