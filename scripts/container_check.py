"""Verify the built container via its real localhost API, without cloud access."""

import argparse
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "reports/container-check.json"
    )
    args = parser.parse_args()
    url = urllib.parse.urlsplit(args.base_url)
    if (
        url.scheme != "http"
        or url.hostname not in {"localhost", "127.0.0.1"}
        or url.path not in {"", "/"}
        or url.query
        or url.fragment
        or url.username
    ):
        parser.error(
            "Use a plain HTTP localhost origin for the isolated test container"
        )
    base = args.base_url.rstrip("/")

    def call(path, method="GET"):
        req = urllib.request.Request(base + path, method=method)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read()
            return (
                json.loads(data)
                if "application/json" in response.headers.get("Content-Type", "")
                else data
            )

    deadline = time.monotonic() + 90
    while True:
        try:
            health = call("/api/health")
            break
        except (OSError, urllib.error.URLError):
            if time.monotonic() > deadline:
                raise RuntimeError("Container never became ready") from None
            time.sleep(1)
    assert health["max_pages"] == 50
    assert not health["gemini"]["configured"], "The image must not contain a cloud key"
    assert b"Choose your AI workflow" in call("/")
    truth = json.loads((ROOT / "samples/ground_truth.json").read_text(encoding="utf-8"))
    checks = []
    for filename, expected in truth.items():
        job = call("/api/samples/" + Path(filename).stem, "POST")["id"]
        deadline = time.monotonic() + 240
        while True:
            state = call(f"/api/jobs/{job}")
            if state["status"] in {"complete", "failed"}:
                break
            if time.monotonic() > deadline:
                raise RuntimeError(f"Container extraction timed out: {filename}")
            time.sleep(0.5)
        assert state["status"] == "complete", state["message"]
        result = call(f"/api/jobs/{job}/result")
        assert result["workflow"] == {"mode": "local"} and "gemini" not in result
        assert len(result["tables"]) == 1
        table = result["tables"][0]
        assert table["headers"] == expected["headers"]
        assert [r["cells"] for r in table["rows"]] == expected["rows"]
        with zipfile.ZipFile(io.BytesIO(call(f"/api/jobs/{job}/export/xlsx"))) as book:
            assert book.testzip() is None
            assert b"Table 1" in book.read("xl/workbook.xml")
        checks.append(
            {
                "sample": filename,
                "rows": len(table["rows"]),
                "cells": sum(map(len, expected["rows"])),
                "headers_exact": True,
                "xlsx_valid": True,
                "workflow": "local",
                "passed": True,
            }
        )
        print(
            f"PASS container: {filename}, exact cells/headers and valid Excel",
            flush=True,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "scope": "Real non-root Docker API: three dummy samples, exact data/headers, Excel and keyless local routing. No hidden or cloud accuracy claim.",
                "checks": checks,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
