"""Atomic JSON persistence shared by jobs, page checkpoints and cloud ledgers."""

import json
import time
import uuid
from contextlib import suppress
from pathlib import Path


def atomic_json(path: Path, data: object) -> None:
    """Keep the previous file intact on serialization, disk or replace failure.

    Each writer gets a unique temporary file. Windows scanners may briefly hold
    the destination without delete sharing, so replacement gets seven bounded
    attempts. Callers serialize concurrent read/modify/write operations themselves.
    This guarantees atomic replacement, not power-loss durability or locking
    between independent processes. Cleanup never masks the original exception.
    """
    payload = json.dumps(data, ensure_ascii=False, allow_nan=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(payload, encoding="utf-8")
        for attempt in range(7):
            try:
                temp.replace(path)
                return
            except PermissionError:
                if attempt == 6:
                    raise
                time.sleep(0.02 * 2**attempt)
    finally:
        with suppress(OSError):
            temp.unlink(missing_ok=True)
