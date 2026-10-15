"""Run the same static quality gates as CI; no documents or cloud API calls."""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    commands = [
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
    ]
    for command in commands:
        completed = subprocess.run(command, cwd=ROOT, check=False)
        if completed.returncode:
            return completed.returncode
    npm = shutil.which("npm")
    if not npm:
        print(
            "Maintainer checks need Node.js/npm. Judges can run the Python app without them.",
            file=sys.stderr,
        )
        return 1
    return subprocess.call([npm, "run", "check"], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
