"""Standard-library bootstrap: install once, diagnose, test, or launch locally."""

import argparse
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
MODELS = {
    "en_PP-OCRv5_rec_mobile.onnx": "c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8",
    "en_PP-OCRv3_rec_infer.onnx": "ef7abd8bd3629ae57ea2c28b425c1bd258a871b93fd2fe7c433946ade9b5d9ea",
    "en_dict.txt": "5662df9d2d03f0e8ca0d3b0649d6acbab904b6a14b3d3521463c71c37c668ce3",
}


def runtime_ready(python):
    """Check installed distributions without contacting a package server."""
    code = """
import importlib.metadata as m
from pathlib import Path
for line in Path('requirements.txt').read_text().splitlines():
    if line.strip() and not line.startswith('#'):
        name, version = line.split('==')
        assert m.version(name) == version, name
import cv2, numpy, pymupdf, rapidocr_onnxruntime, openpyxl, uvicorn, multipart
"""
    if not Path(python).exists():
        return False
    result = subprocess.run(
        [str(python), "-c", code], cwd=ROOT, capture_output=True, text=True
    )
    if result.returncode:
        errors = result.stderr.strip().splitlines()
        print(
            "Runtime needs setup:",
            errors[-1] if errors else f"Python exited with code {result.returncode}",
        )
    return result.returncode == 0


def check_assets():
    for name, expected in MODELS.items():
        path = ROOT / "models" / name
        if (
            not path.exists()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise RuntimeError(
                f"Bundled OCR asset is missing or damaged: models/{name}. Download the complete repository archive again."
            )
    import tempfile

    with tempfile.TemporaryFile(dir=ROOT):
        pass
    print("PASS: bundled English OCR model, dictionary and writable project folder.")


def main():
    parser = argparse.ArgumentParser(description="DamnLens AI Agent judge setup")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--check", action="store_true", help="Diagnose only; no installation or launch"
    )
    group.add_argument(
        "--setup-only",
        action="store_true",
        help="Prepare the runtime without opening the app",
    )
    group.add_argument(
        "--judge-test",
        action="store_true",
        help="Run cell comparisons, export and boundary checks",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Never run pip; require existing dependencies",
    )
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    if sys.version_info < (3, 12) or struct.calcsize("P") != 8:
        raise RuntimeError(
            "Install 64-bit Python 3.12 from https://www.python.org/downloads/ and retry. No administrator rights are required if installed for your user."
        )
    print("DamnLens AI Agent | local judge setup", flush=True)
    check_assets()
    ready = runtime_ready(PYTHON)
    if not ready and args.check:
        raise RuntimeError(
            "Runtime is not ready. Run START_DAMNLENS.cmd (Windows) or ./start.sh (macOS/Linux) once while connected to the internet."
        )
    if not ready and args.offline:
        raise RuntimeError(
            "Offline mode cannot install missing dependencies. Run setup once online, then retry --offline."
        )
    if not ready:
        if not PYTHON.exists():
            print("Creating a project-local virtual environment...", flush=True)
            try:
                venv.EnvBuilder(with_pip=True).create(ROOT / ".venv")
            except Exception as exc:
                raise RuntimeError(
                    "Could not create the environment. On Debian/Ubuntu install python3-venv; on Windows use the full python.org installation. "
                    + str(exc)
                ) from exc
        print(
            "Installing pinned dependencies. First setup requires internet; later launches do not.",
            flush=True,
        )
        subprocess.run(
            [
                str(PYTHON),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-r",
                "requirements.txt",
            ],
            cwd=ROOT,
            check=True,
        )
        if not runtime_ready(PYTHON):
            raise RuntimeError(
                "Dependency verification failed. On Linux install libgl1 and libglib2.0-0. See README troubleshooting."
            )
    print(
        "PASS: pinned dependencies and native libraries load successfully.", flush=True
    )
    if args.check or args.setup_only:
        return 0
    if args.judge_test:
        return subprocess.call([str(PYTHON), "scripts/judge_check.py"], cwd=ROOT)
    command = [str(PYTHON), "run.py"]
    if args.no_browser:
        command.append("--no-browser")
    if args.port is not None:
        command.extend(["--port", str(args.port)])
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(
            f"\nSETUP FAILED: {exc}\nSee README.md for manual setup and troubleshooting.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(130)
