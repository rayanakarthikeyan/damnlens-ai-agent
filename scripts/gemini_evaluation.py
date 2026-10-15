"""Opt-in live check of one dummy sample page, one request maximum.

Unlike tests/test_gemini.py, this sends data to Google and may incur charges.
The first ten ground-truth rows are page 1 in all three bundled generators.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.gemini import load_environment  # noqa: E402
from app.workflow import options, run  # noqa: E402


def evaluate_result(sample, result):
    assist = result["gemini"]
    page = assist.get("pages", [{}])[0]
    truth = json.loads(
        (ROOT / "samples/ground_truth.json").read_text(encoding="utf-8")
    )[f"{sample}.pdf"]
    expected = truth["rows"][:10]
    tables = page.get("tables", [])
    actual = tables[0]["rows"] if len(tables) == 1 else []

    def normalize(value):
        return " ".join(value.split())

    matching = sum(
        normalize(a) == normalize(b)
        for ar, er in zip(actual, expected, strict=False)
        for a, b in zip(ar, er, strict=False)
    )
    denominator = max(sum(map(len, actual)), sum(map(len, expected)))
    report = {
        "at": datetime.now(timezone.utc).isoformat(),
        "kind": "live API, original dummy fixture, first page only",
        "sample": sample,
        "source_sha256": result["sha256"],
        "model": result["workflow"]["model"],
        "request_limit": 1,
        "requests_used": assist.get("requests_used", 0),
        "input_mime_type": page.get("input_mime_type", "application/pdf"),
        "provider_status": page.get("status", "unavailable"),
        "message": page.get("message", assist.get("message", "")),
        "usage": page.get("usage", {}),
        "candidate_tables": len(tables),
        "matching_data_cells": matching,
        "checked_cell_denominator": denominator,
        "expected_shape": [10, 12],
        "actual_shape": [len(actual), len(actual[0]) if actual else 0],
        "headers_exact": len(tables) == 1 and tables[0]["headers"] == truth["headers"],
        "local_rows_preserved": result["row_count"],
        "scope": "Single non-blind dummy page. No hidden-PDF, cost invoice or general accuracy claim.",
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sample",
        choices=["01_invoice_register", "02_scanned_inventory", "03_bank_statement"],
        default="01_invoice_register",
    )
    parser.add_argument(
        "--allow-cloud",
        action="store_true",
        help="Authorize sending the dummy page to Google (required)",
    )
    parser.add_argument(
        "--key-stdin",
        action="store_true",
        help="Read key from a private input pipe; never saved or echoed",
    )
    args = parser.parse_args()
    if not args.allow_cloud:
        parser.error("--allow-cloud is required; this is a real API request")
    if args.key_stdin:
        import getpass

        if sys.stdin.isatty():
            os.environ["GEMINI_API_KEY"] = getpass.getpass("API key (hidden): ").strip()
        else:
            os.environ["GEMINI_API_KEY"] = sys.stdin.readline().strip()
        if not os.environ["GEMINI_API_KEY"]:
            parser.error(
                "No key received; use a terminal prompt or the launch environment"
            )
    load_environment(ROOT)
    config = options("gemini", True, "all", 1)
    print(f"Live dummy-page check: {args.sample}; at most one request.", flush=True)
    result = run(ROOT / "samples" / f"{args.sample}.pdf", config)
    report = evaluate_result(args.sample, result)
    target = ROOT / "reports" / f"gemini-live-{args.sample}.json"
    target.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    private = ROOT / "tmp" / f"gemini-live-{args.sample}-result.json"
    private.parent.mkdir(exist_ok=True)
    private.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    print(f"Report: {target.name}", flush=True)
    return 0 if report["provider_status"] == "checked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
