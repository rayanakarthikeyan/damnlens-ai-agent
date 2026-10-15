"""Headless conversion: python convert.py input.pdf -o output.xlsx."""

import argparse
import json
from pathlib import Path

from app.exporter import xlsx
from app.gemini import load_environment, save_ledger
from app.workflow import options, run


def main():
    p = argparse.ArgumentParser(
        description="Convert a PDF or image to a validated Excel workbook"
    )
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path)
    p.add_argument("--force-ocr", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--workflow", choices=["local", "gemini"], default="local")
    p.add_argument(
        "--allow-cloud",
        action="store_true",
        help="Authorize selected source pages being sent to Google",
    )
    p.add_argument("--gemini-scope", choices=["flagged", "all"], default="flagged")
    p.add_argument("--max-requests", type=int, default=3)
    p.add_argument(
        "--gemini-ledger",
        type=Path,
        help="Cloud reservation/candidate ledger; defaults beside output. Reusing it never grants a fresh budget.",
    )
    args = p.parse_args()
    out = args.output or args.input.with_suffix(".xlsx")
    if out.resolve() == args.input.resolve():
        p.error("Output must differ from input")
    if out.suffix.lower() != ".xlsx":
        p.error("Excel output must use the .xlsx extension")
    sidecar = out.with_suffix(".json") if args.json else None
    ledger = args.gemini_ledger or out.with_suffix(out.suffix + ".gemini-ledger.json")
    if args.workflow == "gemini" and ledger.resolve() in {
        path.resolve() for path in (args.input, out, sidecar) if path is not None
    }:
        p.error("Gemini ledger must differ from input, Excel output and JSON output")
    try:
        load_environment(Path(__file__).resolve().parent)
        workflow = options(
            args.workflow, args.allow_cloud, args.gemini_scope, args.max_requests
        )
        r = run(
            args.input,
            workflow=workflow,
            ledger_path=ledger if args.workflow == "gemini" else None,
            save=save_ledger,
            progress=lambda d, t, m: print(f"[{d}/{t}] {m}", flush=True),
            force_ocr=args.force_ocr,
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(xlsx(r))
        if args.json:
            out.with_suffix(".json").write_text(
                json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        print(
            f"Saved {out}: {len(r['tables'])} tables, {r['row_count']} rows, {len(r['issues'])} findings."
        )
        if not r["tables"]:
            raise SystemExit(2)
    except (ValueError, RuntimeError, OSError) as exc:
        p.exit(1, f"Conversion failed: {exc}\n")


if __name__ == "__main__":
    main()
