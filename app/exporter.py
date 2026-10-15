"""Typed, traceable Excel output. Never execute source text as a formula."""

import csv
import io
import re
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from .engine import number, norm

NAVY = "182D35"
TEAL = "117B70"
PALE = "EAF5F1"
AMBER = "FFF0D5"
RED = "FDE7E3"


def typed(text, header):
    key = norm(header)
    if key in {
        "id",
        "sku",
        "code",
        "account",
        "reference",
        "phone",
        "zip",
        "postal",
        "invoice",
        "number",
    } or key.endswith(
        (
            "number",
            "reference",
            "sku",
            "code",
            "itemid",
            "invoiceid",
            "accountid",
            "transactionid",
            "invoiceno",
            "accountno",
        )
    ):
        return text
    if "date" in key:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                pass
        return text
    if re.fullmatch(r"0\d+", text):
        return text
    value = number(text)
    if value is not None:
        return value / 100 if "%" in text else value
    return text


def safe_cell(cell, value):
    cell.value = value
    if isinstance(value, str):
        cell.data_type = "s"
    return cell


def style(ws, table_name=None):
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    ws.row_dimensions[1].height = 30
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.font = Font(name="Aptos", color="FFFFFF", bold=True, size=11)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = Font(name="Aptos", size=11, color=NAVY)
            c.alignment = Alignment(vertical="top", wrap_text=True)
            if c.row % 2 == 0:
                c.fill = PatternFill("solid", fgColor="F2F7F5")
        ws.row_dimensions[row[0].row].height = 30
    for col in ws.columns:
        length = max(len(str(c.value or "")) for c in list(col)[:100])
        ws.column_dimensions[col[0].column_letter].width = min(65, max(16, length + 3))
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A3
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_title_rows = "1:1"
    if table_name and ws.max_row > 1:
        table = Table(displayName=table_name, ref=ws.dimensions)
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2", showRowStripes=True
        )
        ws.add_table(table)


def xlsx(result):
    wb = Workbook()
    summary = wb.active
    summary.title = "Overview"
    summary.append(["LedgerLens extraction report", "Value"])
    for item in [
        ("Document", result["filename"]),
        ("Pages", result["page_count"]),
        ("Tables", len(result["tables"])),
        ("Extracted rows", result["row_count"]),
        ("Repeated headers removed", result["headers_removed"]),
        ("Validation findings", len(result["issues"])),
        ("Processing seconds", result["elapsed_seconds"]),
        ("Source SHA-256", result["sha256"]),
        ("Engine", result["engine"]),
        (
            "Interpretation",
            "OCR recognition scores are not measured extraction accuracy. Review all findings.",
        ),
        (
            "Coverage",
            "Pages without extracted tables are explicitly flagged. No guarantee for arbitrary layouts.",
        ),
    ]:
        summary.append(item)
    style(summary)
    summary.column_dimensions["A"].width = 32
    summary.column_dimensions["B"].width = 85
    for t in result["tables"]:
        ws = wb.create_sheet(f"Table {t['id']}")
        ws.append(
            t["headers"]
            + ["Source page", "Source row", "Extraction method", "OCR score"]
        )
        for r in t["rows"]:
            row = ws.max_row + 1
            for i, (h, value) in enumerate(zip(t["headers"], r["cells"]), 1):
                cell = safe_cell(ws.cell(row, i), typed(value, h))
                if isinstance(cell.value, datetime):
                    cell.number_format = "yyyy-mm-dd"
                elif isinstance(cell.value, (float, int)):
                    cell.number_format = "0.00%" if "%" in value else "#,##0.00"
            for i, v in enumerate(
                [r["page"], r["id"], r["method"], r["confidence"]],
                len(t["headers"]) + 1,
            ):
                safe_cell(ws.cell(row, i), v)
        style(ws, f"Extracted{t['id']}")
        for issue in result["issues"]:
            if issue["table"] == t["id"] and issue["row"]:
                cols = (
                    [issue["column"]]
                    if issue["column"]
                    else range(1, len(t["headers"]) + 1)
                )
                for col in cols:
                    ws.cell(issue["row"] + 1, col).fill = PatternFill(
                        "solid", fgColor=RED if issue["severity"] == "error" else AMBER
                    )
    checks = wb.create_sheet("Validation")
    checks.append(["Severity", "Table", "Row", "Column", "Check", "Finding"])
    for issue in result["issues"]:
        checks.append(
            [
                issue.get(k)
                for k in ["severity", "table", "row", "column", "kind", "message"]
            ]
        )
    if not result["issues"]:
        checks.append(
            [
                "info",
                None,
                None,
                None,
                "complete",
                "No issues found by the implemented checks. Manual review remains necessary.",
            ]
        )
    style(checks)
    checks.column_dimensions["F"].width = 90
    evidence = wb.create_sheet("Evidence")
    evidence.append(
        [
            "Table",
            "Row",
            "Page",
            "Bounding box (PDF points)",
            "Method",
            "Recognition score",
        ]
    )
    for t in result["tables"]:
        for r in t["rows"]:
            evidence.append(
                [
                    t["id"],
                    r["id"],
                    r["page"],
                    str(r["bbox"]),
                    r["method"],
                    r["confidence"],
                ]
            )
    style(evidence)
    edits = wb.create_sheet("Corrections")
    edits.append(["Table", "Row", "Column", "Original", "Edited", "Time (UTC)"])
    for e in result["edits"]:
        edits.append(
            [e.get(k) for k in ["table", "row", "column", "before", "after", "at"]]
        )
    style(edits)
    # Harden every sheet, including names, validation text and correction history.
    for ws in wb:
        for row in ws:
            for c in row:
                if isinstance(c.value, str):
                    c.data_type = "s"
    stream = io.BytesIO()
    wb.save(stream)
    return stream.getvalue()


def csv_bytes(table):
    out = io.StringIO(newline="")
    writer = csv.writer(out)

    def safe(s):
        return "'" + s if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else s

    writer.writerow([safe(s) for s in table["headers"]])
    writer.writerows([[safe(s) for s in r["cells"]] for r in table["rows"]])
    return out.getvalue().encode("utf-8-sig")
