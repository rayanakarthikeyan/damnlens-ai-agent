"""Deterministic extraction orchestration; document content is always treated as data."""

from __future__ import annotations

import hashlib
import re
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from difflib import SequenceMatcher
from pathlib import Path
from threading import Lock

from .quality import enrich
from .checkpoints import PageCheckpoints
from .layout import (
    grid_records,
    prepare_fragment,
    append_continuation,
    aligned_fragments,
    native_cell_text,
)

import cv2
import numpy as np
import pymupdf as fitz

OCR_LOCK = Lock()
_ocr = None
HEADER_WORDS = {
    "date",
    "description",
    "amount",
    "balance",
    "quantity",
    "qty",
    "price",
    "total",
    "debit",
    "credit",
    "sku",
    "item",
    "account",
    "reference",
    "tax",
    "net",
    "unit",
    "id",
    "region",
    "name",
    "city",
    "country",
    "status",
    "category",
    "code",
    "count",
    "sales",
    "revenue",
    "department",
    "score",
    "product",
    "invoice",
    "cost",
}


def clean(value):
    return re.sub(r"\s+", " ", str("" if value is None else value)).strip()


def norm(value):
    return re.sub(r"[^a-z0-9]", "", clean(value).lower())


def decimal_number(value):
    """Parse unambiguous decimal amounts; preserve identifiers in the exporter."""
    text = clean(value).replace("−", "-").replace("\u00a0", "")
    if not text or text in {"-", "—", "N/A"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"^(?:USD|INR|EUR|GBP)\s*", "", text, flags=re.I)
    text = re.sub(r"[$₹€£%()\s]", "", text)
    if "," in text and "." in text:
        text = (
            text.replace(".", "").replace(",", ".")
            if text.rfind(",") > text.rfind(".")
            else text.replace(",", "")
        )
    elif "," in text:
        text = (
            text.replace(",", "")
            if re.fullmatch(r"-?\d{1,3}(?:,\d{3})+|-?\d{1,2}(?:,\d{2})*,\d{3}", text)
            else text.replace(",", ".")
        )
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
        return None
    result = Decimal(text)
    return -result if negative else result


def number(value):
    result = decimal_number(value)
    return float(result) if result is not None else None


def is_header(row):
    filled = [c for c in row if clean(c)]
    words = set(re.findall(r"[a-z]+", " ".join(filled).lower()))
    return (
        len(words & HEADER_WORDS) >= 2
        and sum(number(c) is not None for c in filled) < len(filled) * 0.4
    )


def unique_headers(row):
    counts = Counter()
    result = []
    for i, c in enumerate(row):
        c = clean(c) or f"Column {i + 1}"
        counts[c] += 1
        result.append(c if counts[c] == 1 else f"{c} ({counts[c]})")
    return result


def header_row_index(rows):
    """Skip an optional sparse spanning label above a real column-header row."""
    for index, row in enumerate(rows[:3]):
        if is_header(row["cells"]):
            preceding = rows[:index]
            if all(
                sum(bool(clean(c)) for c in r["cells"]) <= max(2, len(r["cells"]) // 3)
                for r in preceding
            ):
                return index
            break
    return None


def record(cells, page, bbox, method, confidence=1.0):
    return {
        "cells": [clean(c) for c in cells],
        "page": page,
        "bbox": [round(float(x), 2) for x in bbox],
        "method": method,
        "confidence": round(float(confidence), 3),
    }


def native_tables(page, page_no):
    candidates = page.find_tables(strategy="lines_strict").tables
    method = "Native PDF · grid"
    if not candidates:
        inferred = aligned_text_tables(page, page_no)
        if inferred:
            return inferred
        candidates = page.find_tables(
            strategy="text", min_words_vertical=3, min_words_horizontal=1
        ).tables
        method = "Native PDF · text alignment"
    out = []
    blocks = page.get_text(
        "dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES
    )["blocks"]
    font_spans = [
        (
            s["bbox"],
            len(s["text"]),
            bool(s["flags"] & 16) or "bold" in s["font"].lower(),
        )
        for b in blocks
        for line in b.get("lines", [])
        for s in line["spans"]
    ]
    raw_blocks = page.get_text(
        "rawdict", flags=fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES
    )["blocks"]
    characters = [
        c
        for block in raw_blocks
        for line in block.get("lines", [])
        for span in line["spans"]
        for c in span["chars"]
    ]
    for table in candidates:
        raw = table.extract()
        if table.col_count < 2 or len(raw) < 2:
            continue
        rows = []
        raw = [
            [native_cell_text(characters, box) if box else None for box in row.cells]
            for row in table.rows
        ]
        if table.header.external:
            header = record(table.header.names, page_no, table.header.bbox, method)
            header["_header_hint"] = True
            rows.append(header)
        rows.extend(
            grid_records(
                raw,
                [r.cells for r in table.rows],
                page_no,
                method,
                record,
                bold_spans=font_spans,
            )
        )
        if len(rows) >= 2:
            context = page.get_text(
                "text",
                clip=fitz.Rect(
                    0, max(0, table.bbox[1] - 110), page.rect.width, table.bbox[1]
                ),
            )
            identifiers = re.findall(
                r"(?:account\s*(?:number|no\.?|id)|invoice\s*(?:number|no\.?))\s*[:#]\s*([\w-]+)",
                context,
                re.I,
            )
            out.append(
                {
                    "rows": rows,
                    "bbox": list(table.bbox),
                    "width": page.rect.width,
                    "context_key": identifiers[-1] if identifiers else None,
                }
            )
    return out


def aligned_text_tables(page, page_no):
    spans = [
        s
        for b in page.get_text(
            "dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES
        )["blocks"]
        for line in b.get("lines", [])
        for s in line["spans"]
    ]
    words = [
        {
            "bbox": list(w[:4]),
            "text": w[4],
            "score": 1.0,
            "bold": any(
                (s["flags"] & 16 or "bold" in s["font"].lower())
                and fitz.Rect(s["bbox"]).contains(
                    fitz.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
                )
                for s in spans
            ),
        }
        for w in page.get_text("words")
    ]
    return aligned_fragments(
        words,
        page.rect.width,
        page_no,
        "Native PDF · inferred columns",
        record,
        is_header,
        number,
    )


def ocr_words(image):
    global _ocr
    with OCR_LOCK:
        if _ocr is None:
            from rapidocr_onnxruntime import RapidOCR

            model_dir = Path(__file__).resolve().parents[1] / "models"
            _ocr = RapidOCR(
                intra_op_num_threads=2,
                inter_op_num_threads=2,
                rec_model_path=str(model_dir / "en_PP-OCRv3_rec_infer.onnx"),
                rec_keys_path=str(model_dir / "en_dict.txt"),
            )
        # Page orientation is preserved; per-word 180-degree classification can
        # incorrectly flip short headers such as "Tax %".
        result, _ = _ocr(image, use_cls=False)
    words = []
    for box, text, score in result or []:
        bbox = [
            min(p[0] for p in box),
            min(p[1] for p in box),
            max(p[0] for p in box),
            max(p[1] for p in box),
        ]
        words.append({"bbox": bbox, "text": text, "score": score})
    return words


def clusters(values, tolerance=8):
    groups = []
    for v in sorted(values):
        if not groups or v - statistics.mean(groups[-1]) > tolerance:
            groups.append([v])
        else:
            groups[-1].append(v)
    return [statistics.mean(g) for g in groups]


def recognize_inked_region(image):
    """Recognition-only fallback for missed glyphs; require two-scale agreement."""
    if image.size == 0:
        return None
    mask = (cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) < 185).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    components = [
        (x, y, w, h)
        for x, y, w, h, area in stats[1:]
        if area >= max(4, mask.size * 0.00012)
        and not (w > mask.shape[1] * 0.8 and h < 5)
        and not (h > mask.shape[0] * 0.8 and w < 5)
    ]
    if not components:
        return None
    left = min(x for x, y, w, h in components)
    top = min(y for x, y, w, h in components)
    right = max(x + w for x, y, w, h in components)
    bottom = max(y + h for x, y, w, h in components)
    crop = image[
        max(0, top - 3) : min(image.shape[0], bottom + 3),
        max(0, left - 3) : min(image.shape[1], right + 3),
    ]
    if crop.size == 0:
        return None
    # ocr_words has already initialized the shared model before this fallback.
    with OCR_LOCK:
        first, _ = _ocr(crop, use_det=False, use_cls=False)
        second, _ = _ocr(
            cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC),
            use_det=False,
            use_cls=False,
        )
    if (
        first
        and second
        and clean(first[0][0]) == clean(second[0][0])
        and min(first[0][1], second[0][1]) >= 0.85
    ):
        return {
            "text": clean(first[0][0]),
            "score": round(min(first[0][1], second[0][1]), 3),
        }
    return None


def orient_scan(image):
    """Try right-angle OCR orientations only when upright evidence is weak.

    Return the inverse transform so evidence still points into the original scan.
    No recognized values are corrected or invented during orientation selection.
    """
    words = ocr_words(image)

    def merit(items):
        centers = clusters([(w["bbox"][1] + w["bbox"][3]) / 2 for w in items], 12)
        header_terms = []
        for y in centers:
            texts = [
                w["text"]
                for w in items
                if abs((w["bbox"][1] + w["bbox"][3]) / 2 - y) <= 12
            ]
            if is_header(texts):
                header_terms.append(
                    len(
                        set(re.findall(r"[a-z]+", " ".join(texts).lower()))
                        & HEADER_WORDS
                    )
                )
        return max(header_terms, default=0), statistics.mean(
            w["score"] for w in items
        ) if items else 0

    best = merit(words)
    inverse = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    if best[0] >= 3 and best[1] >= 0.88:
        return image, words, inverse, 0
    # Prose with good recognition and no tabular header does not need 3 retries.
    if best[0] == 0 and best[1] >= 0.94:
        return image, words, inverse, 0
    height, width = image.shape[:2]
    chosen, angle = image, 0
    candidates = [
        (180, cv2.ROTATE_180, [[-1, 0, width - 1], [0, -1, height - 1]]),
        (90, cv2.ROTATE_90_CLOCKWISE, [[0, 1, 0], [-1, 0, height - 1]]),
        (270, cv2.ROTATE_90_COUNTERCLOCKWISE, [[0, -1, width - 1], [1, 0, 0]]),
    ]
    for rotation, code, mapping in candidates:
        candidate = cv2.rotate(image, code)
        recognized = ocr_words(candidate)
        score = merit(recognized)
        if score > best:
            chosen, words, inverse, best, angle = (
                candidate,
                recognized,
                np.array(mapping, dtype=float),
                score,
                rotation,
            )
        if best[0] >= 3 and best[1] >= 0.94:
            break
    return chosen, words, inverse, angle


def scan_tables(page, page_no, dpi=220):
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
    image = (
        np.frombuffer(pix.samples, dtype=np.uint8)
        .reshape(pix.height, pix.width, 3)
        .copy()
    )
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    image, words, orientation_inverse, orientation = orient_scan(image)
    # Correct modest scan skew before both text recognition and grid detection.
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    bw = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15
    )
    lines = cv2.HoughLinesP(
        bw, 1, np.pi / 1800, 100, minLineLength=image.shape[1] // 4, maxLineGap=20
    )
    angles = []
    for line in [] if lines is None else np.asarray(lines).reshape(-1, 4):
        x1, y1, x2, y2 = line
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(angle) < 7:
            angles.append(angle)
    angle = statistics.median(angles) if angles else 0
    transform = cv2.getRotationMatrix2D(
        (image.shape[1] / 2, image.shape[0] / 2), angle, 1
    )
    if abs(angle) > 0.15:
        image = cv2.warpAffine(
            image,
            transform,
            (image.shape[1], image.shape[0]),
            borderValue=(255, 255, 255),
        )
    deskew_inverse = (
        cv2.invertAffineTransform(transform)
        if abs(angle) > 0.15
        else np.array([[1, 0, 0], [0, 1, 0]])
    )
    # Deskew changes word positions; recognize again only when it was applied.
    if abs(angle) > 0.15:
        words = ocr_words(image)
    inverse = (
        np.vstack([orientation_inverse, [0, 0, 1]])
        @ np.vstack([deskew_inverse, [0, 0, 1]])
    )[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    bw = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15
    )
    h = cv2.morphologyEx(
        bw, cv2.MORPH_OPEN, np.ones((1, max(30, image.shape[1] // 25)), np.uint8)
    )
    v = cv2.morphologyEx(
        bw, cv2.MORPH_OPEN, np.ones((max(30, image.shape[0] // 30), 1), np.uint8)
    )
    grid = cv2.dilate(cv2.bitwise_or(h, v), np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    scale = 72 / dpi

    def original_box(box):
        pts = np.array(
            [[[box[0], box[1]], [box[2], box[1]], [box[2], box[3]], [box[0], box[3]]]],
            dtype=np.float32,
        )
        pts = cv2.transform(pts, inverse)[0] * scale
        return [
            float(pts[:, 0].min()),
            float(pts[:, 1].min()),
            float(pts[:, 0].max()),
            float(pts[:, 1].max()),
        ]

    out = []
    for contour in sorted(contours, key=lambda c: cv2.boundingRect(c)[1]):
        x, y, w, height = cv2.boundingRect(contour)
        if w < image.shape[1] * 0.25 or height < 50:
            continue
        xs = clusters(
            (
                np.where(
                    (v[y : y + height, x : x + w] > 0).sum(axis=0) > height * 0.45
                )[0]
                + x
            ).tolist()
        )
        ys = clusters(
            (
                np.where((h[y : y + height, x : x + w] > 0).sum(axis=1) > w * 0.45)[0]
                + y
            ).tolist()
        )
        if len(xs) < 3 or len(ys) < 3:
            continue
        rows = []
        for band_index, (top, bottom) in enumerate(zip(ys, ys[1:])):
            separators = [0]
            for col, edge in enumerate(xs[1:-1], 1):
                section = v[
                    int(top) + 5 : int(bottom) - 4, int(edge) - 2 : int(edge) + 3
                ]
                if section.size and (section > 0).any(axis=1).mean() > 0.45:
                    separators.append(col)
            separators.append(len(xs) - 1)
            cells = [""] * (len(xs) - 1)
            scores = []
            cell_scores = [None] * len(cells)
            spans = []
            recognition_retries = []
            for start_col, end_col in zip(separators, separators[1:]):
                left, right = xs[start_col], xs[end_col]
                selected = [
                    a
                    for a in words
                    if left <= (a["bbox"][0] + a["bbox"][2]) / 2 < right
                    and top <= (a["bbox"][1] + a["bbox"][3]) / 2 < bottom
                ]
                selected.sort(key=lambda a: (round(a["bbox"][1] / 12), a["bbox"][0]))
                # Retry visibly inked empty regions, including an isolated digit.
                if not selected:
                    crop = image[
                        int(top) + 5 : int(bottom) - 4, int(left) + 5 : int(right) - 4
                    ]
                    if (
                        crop.size
                        and (cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) < 140).mean()
                        >= 0.004
                    ):
                        retry = ocr_words(
                            cv2.copyMakeBorder(
                                crop,
                                12,
                                12,
                                12,
                                12,
                                cv2.BORDER_CONSTANT,
                                value=(255, 255, 255),
                            )
                        )
                        if retry and all(w["score"] >= 0.75 for w in retry):
                            selected = sorted(retry, key=lambda w: w["bbox"][0])
                if not selected:
                    crop = image[
                        int(top) + 6 : int(bottom) - 5, int(left) + 6 : int(right) - 5
                    ]
                    recovered = recognize_inked_region(crop)
                    if recovered:
                        selected = [recovered]
                        recognition_retries.append(
                            {
                                "column": start_col + 1,
                                "route": "recognition-only consensus",
                                "score": recovered["score"],
                            }
                        )
                cells[start_col] = " ".join(a["text"] for a in selected)
                scores.extend(a["score"] for a in selected)
                if selected:
                    cell_scores[start_col] = round(min(a["score"] for a in selected), 3)
                if end_col - start_col > 1:
                    spans.append(
                        {
                            "column": start_col + 1,
                            "column_span": end_col - start_col,
                            "row_span": 1,
                            "bbox": original_box([left, top, right, bottom]),
                            "value": cells[start_col],
                        }
                    )
            if any(cells):
                row = record(
                    cells,
                    page_no,
                    original_box([xs[0], top, xs[-1], bottom]),
                    "OCR · grid"
                    + (f" · rotated {orientation}°" if orientation else ""),
                    statistics.mean(scores) if scores else 0,
                )
                row["cell_confidence"] = cell_scores
                if recognition_retries:
                    row["ocr_retries"] = recognition_retries
                if spans:
                    row["merged_cells"] = spans
                if rows and band_index > 0:
                    for col, (left, right) in enumerate(zip(xs, xs[1:])):
                        if (
                            cells[col]
                            or not rows[-1]["cells"][col]
                            or number(rows[-1]["cells"][col]) is not None
                        ):
                            continue
                        boundary = h[
                            int(top) - 2 : int(top) + 3, int(left) + 5 : int(right) - 4
                        ]
                        if boundary.size and (boundary > 0).any(axis=0).mean() < 0.2:
                            value = rows[-1]["cells"][col]
                            prior = next(
                                (
                                    item
                                    for item in rows[-1].get("inherited_cells", [])
                                    if item["column"] == col + 1
                                ),
                                None,
                            )
                            origin = prior["from_grid_row"] if prior else band_index
                            source_box = original_box(
                                [left, ys[origin - 1], right, bottom]
                            )
                            row["cells"][col] = value
                            row.setdefault("inherited_cells", []).append(
                                {
                                    "column": col + 1,
                                    "from_page": page_no,
                                    "from_grid_row": origin,
                                    "bbox": source_box,
                                    "value": value,
                                }
                            )
                rows.append(row)
        if rows:
            out.append(
                {
                    "rows": rows,
                    "bbox": original_box([x, y, x + w, y + height]),
                    "width": page.rect.width,
                }
            )
    if out:
        return out
    inferred = aligned_fragments(
        words,
        image.shape[1],
        page_no,
        "OCR · inferred columns",
        record,
        is_header,
        number,
        original_box,
        lambda box: recognize_inked_region(
            image[
                max(0, int(box[1])) : min(image.shape[0], int(box[3])),
                max(0, int(box[0])) : min(image.shape[1], int(box[2])),
            ]
        ),
    )
    for fragment in inferred:
        fragment["width"] = page.rect.width
    return inferred


def stitch(fragments):
    tables = []
    for frag in fragments:
        max_columns = max(len(r["cells"]) for r in frag["rows"])
        ragged = any(len(r["cells"]) != max_columns for r in frag["rows"])
        for row in frag["rows"]:
            row["cells"] += [""] * (max_columns - len(row["cells"]))
        frag = prepare_fragment(frag, is_header, number)
        rows = frag["rows"]
        header_index = None if frag.get("has_header") else header_row_index(rows)
        if header_index is not None and header_index > 0:
            rows = rows[header_index:]
        first = rows[0]["cells"]
        has_header = frag.get("has_header", is_header(first))
        headers = (
            unique_headers(first)
            if has_header
            else [f"Column {i + 1}" for i in range(len(first))]
        )
        data = rows[1:] if has_header else rows
        previous = None
        compatible = []
        x = frag["bbox"][0] / frag["width"]
        y = frag["bbox"][1] / frag["width"]
        width = (frag["bbox"][2] - frag["bbox"][0]) / frag["width"]
        # Match every eligible table from the preceding page, rather than only
        # the last table. A table already extended onto this page is ineligible.
        for candidate in reversed(tables):
            if (
                candidate.get("header_paths")
                and frag.get("header_paths")
                and [[norm(s) for s in p] for p in candidate["header_paths"]]
                != [[norm(s) for s in p] for p in frag["header_paths"]]
            ):
                continue
            if (
                frag.get("context_key")
                and candidate.get("context_key")
                and frag["context_key"] != candidate["context_key"]
            ):
                continue
            if candidate["pages"][-1] + 1 != rows[0]["page"] or len(
                candidate["headers"]
            ) != len(headers):
                continue
            if abs(x - candidate["_x"]) >= 0.04 or abs(width - candidate["_w"]) >= 0.04:
                continue
            if has_header:
                matches = sum(
                    SequenceMatcher(None, norm(a), norm(b)).ratio() > 0.82
                    for a, b in zip(candidate["headers"], headers)
                )
                if (
                    matches / len(headers) < 0.9
                    or SequenceMatcher(
                        None, norm(candidate["headers"][0]), norm(headers[0])
                    ).ratio()
                    < 0.75
                ):
                    continue
            compatible.append(candidate)
        if compatible:
            previous = min(compatible, key=lambda candidate: abs(y - candidate["_y"]))
        if previous is not None:
            target = previous
            target["headers_removed"] += frag.get("header_depth", int(has_header))
        else:
            target = {
                "id": len(tables) + 1,
                "name": f"Table {len(tables) + 1}",
                "headers": headers,
                "rows": [],
                "pages": [],
                "headers_removed": 0,
                "inferred_headers": not has_header,
                "_x": frag["bbox"][0] / frag["width"],
                "_y": y,
                "_w": (frag["bbox"][2] - frag["bbox"][0]) / frag["width"],
            }
            tables.append(target)
            if frag.get("context_key"):
                target["context_key"] = frag["context_key"]
            if frag.get("header_paths"):
                target["header_paths"] = frag["header_paths"]
                target["header_rows"] = frag["header_rows"]
        if ragged:
            target["ragged_rows"] = True
        for row_index, row in enumerate(data):
            if [norm(c) for c in row["cells"]] == [norm(c) for c in target["headers"]]:
                target["headers_removed"] += 1
                continue
            row["cells"] = row["cells"] + [""] * (len(headers) - len(row["cells"]))
            if (
                row_index == 0
                and previous is not None
                and append_continuation(target, row)
            ):
                continue
            row["id"] = len(target["rows"]) + 1
            target["rows"].append(row)
        target["pages"] = sorted(set(target["pages"] + [r["page"] for r in rows]))
    for t in tables:
        t.pop("_x")
        t.pop("_y")
        t.pop("_w")
    return tables


def validate(tables):
    issues = []

    def add(t, kind, message, row=None, col=None, severity="warning"):
        issues.append(
            {
                "id": len(issues) + 1,
                "table": t["id"],
                "row": row,
                "column": col,
                "kind": kind,
                "severity": severity,
                "message": message,
            }
        )

    for t in tables:
        rows = t["rows"]
        headers = t["headers"]
        n = len(headers)
        if t.get("inferred_headers"):
            add(
                t,
                "header_review",
                "Headers could not be identified. Generic column names need review.",
            )
        if t.get("ragged_rows"):
            add(
                t,
                "alignment_review",
                "Source rows have different column counts. Extra columns were preserved with explicit headers; verify alignment.",
            )
        if not t.get("inferred_headers") and any(
            re.fullmatch(r"Column \d+(?: \(\d+\))?", h) for h in headers
        ):
            add(
                t,
                "header_review",
                "Some column names could not be identified. Source values and extra columns remain preserved.",
            )
        if rows and any("inferred" in r["method"] for r in rows):
            add(
                t,
                "alignment_review",
                "Borderless column positions were inferred from aligned text. Verify alignment against the source.",
            )
        seen = {}
        numeric_cols = []
        normal_rows = [
            r
            for r in rows
            if not any(
                re.fullmatch(r"(?:grand\s+|sub\s*)?total(?:\s*[:\-])?", c, re.I)
                for c in r["cells"][:3]
            )
        ]
        dense_cols = [
            c
            for c in range(n)
            if normal_rows
            and sum(bool(r["cells"][c]) for r in normal_rows) / len(normal_rows) >= 0.9
        ]
        for c, h in enumerate(headers):
            values = [r["cells"][c] for r in rows if r["cells"][c]]
            if not values:
                add(t, "empty_column", f'Column "{h}" is completely empty.', col=c + 1)
            if (
                values
                and sum(number(v) is not None for v in values) / len(values) > 0.7
            ):
                numeric_cols.append(c)
        sums = {c: 0 for c in numeric_cols}
        sum_counts = {c: 0 for c in numeric_cols}
        section_sums = {c: 0 for c in numeric_cols}
        section_counts = {c: 0 for c in numeric_cols}
        for r in rows:
            cells = r["cells"]
            rid = r["id"]
            if r.get("ocr_retries"):
                add(
                    t,
                    "ocr_retry_review",
                    "A missed inked cell was recovered by recognition-only OCR with two-scale agreement. Verify against the source.",
                    rid,
                )
            if r.get("continued_across_pages"):
                add(
                    t,
                    "row_continuation",
                    "Description-only page-boundary fragments were joined. Verify both source parts.",
                    rid,
                )
            for inherited in r.get("inherited_cells", []):
                add(
                    t,
                    "merged_cell_review",
                    "Value is shared by an explicit vertically merged source cell; source geometry is retained.",
                    rid,
                    inherited["column"],
                )
            for span in r.get("merged_cells", []):
                if span["column_span"] > 1:
                    add(
                        t,
                        "merged_cell_review",
                        "A data cell spans multiple source columns. Its text remains in the anchor column; covered columns are not guessed.",
                        rid,
                        span["column"],
                    )
            key = tuple(cells)
            if key in seen:
                add(
                    t,
                    "duplicate_row",
                    f"Identical to row {seen[key]}; preserved for review.",
                    rid,
                )
            seen[key] = rid
            minimum_cell = min(
                (c for c in r.get("cell_confidence", []) if c is not None),
                default=r["confidence"],
            )
            if r["confidence"] < 0.88 or minimum_cell < 0.88:
                add(
                    t,
                    "low_ocr",
                    f"OCR row mean {r['confidence']:.0%}; minimum cell score {minimum_cell:.0%}. Check source.",
                    rid,
                )
            if sum(bool(c) for c in cells) < n * 0.4:
                add(
                    t,
                    "sparse_row",
                    "Most cells are empty; possible merged or shifted row.",
                    rid,
                )
            total = any(
                re.fullmatch(r"(?:grand\s+|sub\s*)?total(?:\s*[:\-])?", c, re.I)
                for c in cells[:3]
            )
            grand_total = any(
                re.fullmatch(r"grand\s+total(?:\s*[:\-])?", c, re.I) for c in cells[:3]
            )
            for c in numeric_cols:
                value = decimal_number(cells[c])
                if total:
                    expected_sum = sums[c] if grand_total else section_sums[c]
                    expected_count = sum_counts[c] if grand_total else section_counts[c]
                    if (
                        value is not None
                        and expected_count
                        and abs(value - expected_sum) > Decimal("0.005")
                    ):
                        add(
                            t,
                            "total_mismatch",
                            f"{headers[c]}: stated {value:,.2f}; preceding rows sum to {expected_sum:,.2f}.",
                            rid,
                            c + 1,
                            "error",
                        )
                elif value is not None:
                    sums[c] += value
                    sum_counts[c] += 1
                    section_sums[c] += value
                    section_counts[c] += 1
                elif cells[c]:
                    add(
                        t,
                        "column_type",
                        f'Non-numeric value in mostly numeric column "{headers[c]}".',
                        rid,
                        c + 1,
                    )
            if total:
                section_sums = {c: 0 for c in numeric_cols}
                section_counts = {c: 0 for c in numeric_cols}
            if not total:
                for c in sorted(set(numeric_cols + dense_cols)):
                    if not cells[c]:
                        add(
                            t,
                            "missing_value",
                            f'Missing value in usually populated column "{headers[c]}".',
                            rid,
                            c + 1,
                        )
            keys = [norm(h) for h in headers]
            qty = next(
                (i for i, h in enumerate(keys) if h in {"quantity", "qty"}), None
            )
            price = next(
                (i for i, h in enumerate(keys) if h in {"unitprice", "price", "rate"}),
                None,
            )
            net = next(
                (
                    i
                    for i, h in enumerate(keys)
                    if h in {"net", "subtotal", "lineamount"}
                ),
                None,
            )
            if not total and None not in (qty, price, net):
                q, p, v = [decimal_number(cells[i]) for i in (qty, price, net)]
                if None not in (q, p, v) and abs(q * p - v) > Decimal("0.005"):
                    add(
                        t,
                        "arithmetic",
                        f"Quantity × unit price = {q * p:,.2f}; {headers[net]} is {v:,.2f}.",
                        rid,
                        net + 1,
                        "error",
                    )
            tax = next(
                (
                    i
                    for i, h in enumerate(keys)
                    if h in {"tax", "taxamount"} and "%" not in headers[i]
                ),
                None,
            )
            line_total = next(
                (i for i, h in enumerate(keys) if h in {"total", "linetotal", "gross"}),
                None,
            )
            if not total and None not in (net, tax, line_total):
                net_value, tax_value, total_value = [
                    decimal_number(cells[i]) for i in (net, tax, line_total)
                ]
                if None not in (net_value, tax_value, total_value) and abs(
                    net_value + tax_value - total_value
                ) > Decimal("0.005"):
                    add(
                        t,
                        "line_total",
                        f"Net + tax = {net_value + tax_value:,.2f}; total is {total_value:,.2f}.",
                        rid,
                        line_total + 1,
                        "error",
                    )
            # Validate running bank balance only when an explicit opening balance exists.
            balance = next((i for i, h in enumerate(keys) if h == "balance"), None)
            debit = next(
                (i for i, h in enumerate(keys) if h in {"debit", "withdrawal"}), None
            )
            credit = next(
                (i for i, h in enumerate(keys) if h in {"credit", "deposit"}), None
            )
            if rid > 1 and None not in (balance, debit, credit) and not total:
                before = decimal_number(rows[rid - 2]["cells"][balance])
                after = decimal_number(cells[balance])
                d = decimal_number(cells[debit])
                cr = decimal_number(cells[credit])
                if None not in (before, after) and (d is not None or cr is not None):
                    expected = before - (d or 0) + (cr or 0)
                    if abs(expected - after) > Decimal("0.005"):
                        add(
                            t,
                            "balance_mismatch",
                            f"Expected running balance {expected:,.2f}; found {after:,.2f}.",
                            rid,
                            balance + 1,
                            "error",
                        )
    return issues


def extract(
    path: Path,
    progress=lambda *a: None,
    force_ocr=False,
    event=lambda *a: None,
    checkpoint_dir=None,
    resume=False,
):
    start = time.perf_counter()
    events = []

    def emit(stage, message, **details):
        entry = {
            "at": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "message": message,
            **details,
        }
        events.append(entry)
        event(entry)

    emit("inspect", "Opened source document", filename=path.name)
    doc = fitz.open(path)
    try:
        if doc.needs_pass:
            raise ValueError(
                "Password-protected PDFs are not supported. Upload an unlocked copy."
            )
        if not doc.is_pdf:
            pdf = fitz.open("pdf", doc.convert_to_pdf())
            doc.close()
            doc = pdf
        if not 1 <= len(doc) <= 50:
            raise ValueError("Documents must contain 1–50 pages.")
        fragments = []
        pages = []
        checkpoints = (
            PageCheckpoints(checkpoint_dir, path, force_ocr) if checkpoint_dir else None
        )
        for i, page in enumerate(doc):
            page_start = time.perf_counter()
            progress(i, len(doc), f"Inspecting page {i + 1}")
            cached = checkpoints.load(i + 1) if checkpoints and resume else None
            if cached:
                fragments.extend(cached["fragments"])
                metadata = cached["page"]
                metadata["resumed"] = True
                metadata["seconds"] = 0
                metadata["attempts"] = metadata["attempts"] + [
                    "verified checkpoint resume"
                ]
                pages.append(metadata)
                emit(
                    "extract",
                    "Resumed page from a verified checkpoint",
                    page=i + 1,
                    tables=metadata["tables"],
                    method=metadata["method"],
                )
                progress(i + 1, len(doc), f"Page {i + 1} resumed")
                continue
            rotation = page.rotation
            original_rect = page.rect
            evidence_transform = page.rotation_matrix
            if rotation:
                # Work in the PDF's text coordinate system, then transform row
                # evidence back into the original viewer orientation.
                page.set_rotation(0)
                emit(
                    "inspect",
                    "Normalized PDF rotation for extraction",
                    page=i + 1,
                    degrees=rotation,
                )
            native = len(page.get_text().strip()) >= 25 and not force_ocr
            emit(
                "inspect",
                "Selected native text extraction"
                if native
                else "Selected OCR extraction",
                page=i + 1,
            )
            attempts = []
            found = []
            if native:
                try:
                    found = native_tables(page, i + 1)
                    attempts.append("native")
                except Exception as exc:
                    attempts.append(
                        f"Native extraction failed: {type(exc).__name__}; retried with OCR"
                    )
            if not found:
                progress(i, len(doc), f"OCR on page {i + 1}")
                attempts.append("ocr")
                emit(
                    "extract", "Running local OCR and layout reconstruction", page=i + 1
                )
                try:
                    found = scan_tables(page, i + 1)
                except Exception as exc:
                    attempts.append(
                        f"OCR failed: {type(exc).__name__}: {str(exc)[:160]}"
                    )
            if rotation:
                for fragment in found:
                    for row in fragment["rows"]:
                        row["bbox"] = [
                            round(v, 2)
                            for v in fitz.Rect(row["bbox"]) * evidence_transform
                        ]
                        for item in row.get("merged_cells", []) + row.get(
                            "inherited_cells", []
                        ):
                            item["bbox"] = [
                                round(v, 2)
                                for v in fitz.Rect(item["bbox"]) * evidence_transform
                            ]
                page.set_rotation(rotation)
            fragments.extend(found)
            emit(
                "extract",
                "Extracted table fragments"
                if found
                else "No tables found; page needs review",
                page=i + 1,
                tables=len(found),
                method="ocr" if "ocr" in attempts else "native",
            )
            pages.append(
                {
                    "page": i + 1,
                    "tables": len(found),
                    "method": "ocr" if "ocr" in attempts else "native",
                    "attempts": attempts,
                    "status": "extracted" if found else "needs_review",
                    "rows": sum(
                        max(0, len(t["rows"]) - int(is_header(t["rows"][0]["cells"])))
                        for t in found
                    ),
                    "seconds": round(time.perf_counter() - page_start, 2),
                    "width": original_rect.width,
                    "height": original_rect.height,
                }
            )
            if checkpoints:
                try:
                    checkpoints.save(i + 1, found, pages[-1])
                except OSError as exc:
                    emit(
                        "extract",
                        "Checkpoint could not be saved; the extraction result is unaffected",
                        page=i + 1,
                        error=type(exc).__name__,
                    )
            progress(i + 1, len(doc), f"Page {i + 1} complete")
        emit(
            "align",
            "Matching table schemas and continuation pages",
            fragments=len(fragments),
        )
        tables = stitch(fragments)
        if any(
            t.get("header_paths")
            or any(
                r.get("sources") or r.get("merged_cells") or r.get("inherited_cells")
                for r in t["rows"]
            )
            for t in tables
        ):
            emit(
                "align",
                "Preserved complex-table structure and source evidence",
                header_groups=sum(bool(t.get("header_paths")) for t in tables),
                continued_rows=sum(
                    bool(r.get("sources")) for t in tables for r in t["rows"]
                ),
            )
        emit(
            "validate",
            "Checking totals, arithmetic, balances and table integrity",
            tables=len(tables),
        )
        issues = validate(tables)
        for p in pages:
            if p["status"] == "needs_review":
                issues.append(
                    {
                        "id": len(issues) + 1,
                        "table": None,
                        "row": None,
                        "column": None,
                        "kind": "page_review",
                        "page": p["page"],
                        "severity": "error",
                        "message": f"Page {p['page']}: no table extracted. Inspect the page; output may be incomplete.",
                    }
                )
        emit(
            "review",
            "Extraction complete; human review is pending",
            findings=len(issues),
            rows=sum(len(t["rows"]) for t in tables),
        )
        return enrich(
            {
                "filename": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "page_count": len(doc),
                "pages": pages,
                "tables": tables,
                "issues": issues,
                "elapsed_seconds": round(time.perf_counter() - start, 2),
                "row_count": sum(len(t["rows"]) for t in tables),
                "headers_removed": sum(t["headers_removed"] for t in tables),
                "engine": "DamnLens AI Agent 1.3 · PyMuPDF + RapidOCR (PP-OCR / ONNX)",
                "edits": [],
                "events": events,
            }
        )
    finally:
        doc.close()
