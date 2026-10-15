"""Headless conversion: python convert.py input.pdf -o output.xlsx."""
import argparse
import json
from pathlib import Path
from app.engine import extract
from app.exporter import xlsx


def main():
    p=argparse.ArgumentParser(description='Convert a PDF or image to a validated Excel workbook')
    p.add_argument('input',type=Path);p.add_argument('-o','--output',type=Path)
    p.add_argument('--force-ocr',action='store_true');p.add_argument('--json',action='store_true')
    args=p.parse_args();out=args.output or args.input.with_suffix('.xlsx')
    if out.resolve()==args.input.resolve():p.error('Output must differ from input')
    try:
        r=extract(args.input,lambda d,t,m:print(f'[{d}/{t}] {m}',flush=True),args.force_ocr)
        out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(xlsx(r))
        if args.json:out.with_suffix('.json').write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding='utf-8')
        print(f'Saved {out}: {len(r["tables"])} tables, {r["row_count"]} rows, {len(r["issues"])} findings.')
        if not r['tables']:raise SystemExit(2)
    except (ValueError,RuntimeError,FileNotFoundError) as exc:p.exit(1,f'Conversion failed: {exc}\n')


if __name__=='__main__':main()
