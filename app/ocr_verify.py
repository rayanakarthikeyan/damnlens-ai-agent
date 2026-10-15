"""Bounded, local second-model checks for short ambiguous scan labels."""

from pathlib import Path
import re
from threading import Lock

import cv2

_model = None
_lock = Lock()


def verify_labels(image, words):
    global _model
    for word in words:
        original = word["text"]
        if not (
            re.match(r"^[ivxlcdm]{1,6}\.(?:\s|$)", original, re.I)
            or re.fullmatch(r"[A-Za-z]{1,3}\.", original)
        ):
            continue
        x0, y0, x1, y1 = map(int, word["bbox"])
        crop = image[
            max(0, y0 - 3) : min(image.shape[0], y1 + 3),
            max(0, x0 - 3) : min(image.shape[1], x1 + 3),
        ]
        if not crop.size:
            continue
        candidates = []
        with _lock:
            if _model is None:
                from rapidocr_onnxruntime import RapidOCR

                _model = RapidOCR(
                    rec_model_path=str(
                        Path(__file__).resolve().parents[1]
                        / "models/en_PP-OCRv5_rec_mobile.onnx"
                    ),
                    rec_keys_path=None,
                    intra_op_num_threads=2,
                    inter_op_num_threads=2,
                )
            for scale in (1, 2):
                test = cv2.resize(crop, None, fx=scale, fy=scale)
                test = cv2.copyMakeBorder(
                    test, 8, 8, 8, 8, cv2.BORDER_CONSTANT, value=(255, 255, 255)
                )
                result, _ = _model(test, use_det=False, use_cls=False)
                candidates.append(result[0] if result else ["", 0])
        texts = [str(c[0]).strip() for c in candidates]
        agreement = (
            texts[0].casefold() == texts[1].casefold()
            and min(c[1] for c in candidates) >= 0.9
        )
        if agreement and texts[0].casefold() == original.casefold():
            continue
        evidence = {
            "original": original,
            "candidates": [
                {"text": str(c[0]), "score": round(float(c[1]), 3)} for c in candidates
            ],
            "model": "PP-OCRv5 English",
            "bbox": word["bbox"],
        }
        if agreement:
            word["text"] = texts[0]
            word["score"] = min(c[1] for c in candidates)
            word["verification"] = evidence
        else:
            # Do not silently select the candidate that looks most plausible.
            word["score"] = min(word["score"], 0.85)
            word["disagreement"] = evidence
    return words
