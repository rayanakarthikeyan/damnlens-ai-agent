"""Small verified page checkpoints, invalidated by source, mode or engine changes."""

import hashlib
import importlib.metadata
import json
from pathlib import Path
import time
import uuid


class PageCheckpoints:
    def __init__(self, directory, source, force_ocr):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        root = Path(__file__).resolve().parents[1]
        digest = hashlib.sha256(source.read_bytes())
        digest.update(str(force_ocr).encode())
        for name in ("engine.py", "layout.py", "checkpoints.py", "ocr_verify.py"):
            digest.update((root / "app" / name).read_bytes())
        for name in (
            "en_PP-OCRv3_rec_infer.onnx",
            "en_dict.txt",
            "en_PP-OCRv5_rec_mobile.onnx",
        ):
            digest.update((root / "models" / name).read_bytes())
        for package in (
            "PyMuPDF",
            "rapidocr-onnxruntime",
            "onnxruntime",
            "opencv-python",
            "numpy",
        ):
            digest.update(f"{package}={importlib.metadata.version(package)}".encode())
        self.signature = digest.hexdigest()

    def load(self, page):
        path = self.directory / f"page-{page:03}.json"
        if not path.exists() or path.stat().st_size > 10_000_000:
            return None
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            payload = envelope["payload"]
            actual = hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode()
            ).hexdigest()
            if (
                envelope["signature"] != self.signature
                or envelope["checksum"] != actual
                or payload["page"]["page"] != page
            ):
                return None
            if payload["page"]["status"] != "extracted":
                return None
            for fragment in payload["fragments"]:
                assert fragment["rows"] and len(fragment["bbox"]) == 4
                for row in fragment["rows"]:
                    assert (
                        row["page"] == page and len(row["bbox"]) == 4 and row["cells"]
                    )
            return payload
        except (ValueError, KeyError, TypeError, AssertionError, OSError):
            return None

    def save(self, page, fragments, metadata):
        if metadata["status"] != "extracted":
            return
        payload = {"fragments": fragments, "page": metadata}
        checksum = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        envelope = {
            "signature": self.signature,
            "checksum": checksum,
            "payload": payload,
        }
        path = self.directory / f"page-{page:03}.json"
        temp = self.directory / f"{path.name}.{uuid.uuid4().hex}.tmp"
        try:
            temp.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
            for attempt in range(7):
                try:
                    temp.replace(path)
                    break
                except PermissionError:
                    if attempt == 6:
                        raise
                    time.sleep(0.02 * 2**attempt)
        finally:
            temp.unlink(missing_ok=True)
