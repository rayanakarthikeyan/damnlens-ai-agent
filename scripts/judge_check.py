"""Judge smoke checks requiring runtime dependencies only, with honest exit codes."""

import io
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pymupdf as fitz
from openpyxl import load_workbook
from app.engine import extract
from app.exporter import xlsx


def main():
    started = time.perf_counter()
    checks = []

    def check(name, operation):
        try:
            detail = operation()
            checks.append({"name": name, "passed": True, "detail": detail})
            print("PASS:", name, "-", detail, flush=True)
        except Exception as exc:
            checks.append({"name": name, "passed": False, "detail": str(exc)})
            print("FAIL:", name, "-", exc, flush=True)

    truth = json.loads((ROOT / "samples/ground_truth.json").read_text())
    for filename, expected in truth.items():

        def fixture(filename=filename, expected=expected):
            result = extract(ROOT / "samples" / filename)
            assert len(result["tables"]) == 1, "Unexpected number of tables"
            table = result["tables"][0]
            assert table["headers"] == expected["headers"], "Header mismatch"
            assert [row["cells"] for row in table["rows"]] == expected["rows"], (
                "Data differs from ground truth"
            )
            if "bank" in filename:
                assert {"balance_mismatch", "total_mismatch", "missing_value"} <= {
                    i["kind"] for i in result["issues"]
                }, "Expected source errors were not detected"
            workbook = load_workbook(io.BytesIO(xlsx(result)))
            assert {
                "Overview",
                "Table 1",
                "Validation",
                "Evidence",
                "Corrections",
                "Page coverage",
                "Run log",
            } <= set(workbook.sheetnames)
            assert workbook["Table 1"].max_row == len(expected["rows"]) + 1
            return f"{len(expected['rows'])} rows x {len(expected['headers'])} columns, exact cells/headers; Excel inspected"

        check(filename, fixture)

    (ROOT / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="damnlens-judge-", dir=ROOT / "tmp"
    ) as temp:
        temp = Path(temp)

        def fifty():
            document = fitz.open()
            with fitz.open(ROOT / "samples/01_invoice_register.pdf") as source:
                for _ in range(50):
                    document.insert_pdf(source, from_page=0, to_page=0)
            path = temp / "fifty.pdf"
            document.save(path)
            document.close()
            result = extract(path)
            expected = truth["01_invoice_register.pdf"]["rows"][:10] * 50
            assert len(result["tables"]) == 1
            assert [r["cells"] for r in result["tables"][0]["rows"]] == expected
            assert result["headers_removed"] == 49
            return "50 pages, 500 rows, 12 columns; 49 headers removed; duplicate business rows preserved"

        check("50-page boundary and duplicate preservation", fifty)

        def rejected():
            document = fitz.open()
            for _ in range(51):
                document.new_page()
            path = temp / "over.pdf"
            document.save(path)
            document.close()
            try:
                extract(path)
            except ValueError as exc:
                assert "50" in str(exc)
                return "51-page input rejected with an actionable message"
            raise AssertionError("An oversized document was accepted")

        check("Over-limit recovery", rejected)

    report = {
        "application": "DamnLens AI Agent",
        "seconds": round(time.perf_counter() - started, 2),
        "scope": "Bundled synthetic samples, XLSX readability and page boundaries. This is a reproducible smoke check, not a hidden-PDF accuracy guarantee.",
        "checks": checks,
    }
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/judge-check-latest.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(
        f"\n{sum(c['passed'] for c in checks)}/{len(checks)} checks passed in {report['seconds']}s. Report: reports/judge-check-latest.json"
    )
    return 0 if all(c["passed"] for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
