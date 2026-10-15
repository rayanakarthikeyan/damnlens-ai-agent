"""Geometry-backed structure recovery; ambiguous source cells stay reviewable.

This module never guesses missing financial values. Only a PDF cell rectangle
spanning multiple grid rows can supply an inherited value. Header group labels
are retained separately even when the leaf labels already form a unique schema.
"""

import re
import statistics
from collections import Counter
from copy import deepcopy


def text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def key(value):
    return re.sub(r"[^a-z0-9]", "", text(value).lower())


def reading_order(words):
    """Cluster baselines before sorting x; fixed y buckets reorder prose."""
    if not words:
        return []
    height = statistics.median(w["bbox"][3] - w["bbox"][1] for w in words)
    lines = []
    for word in sorted(words, key=lambda w: (w["bbox"][1] + w["bbox"][3]) / 2):
        center = (word["bbox"][1] + word["bbox"][3]) / 2
        if (
            not lines
            or center
            - statistics.mean((w["bbox"][1] + w["bbox"][3]) / 2 for w in lines[-1])
            > height * 0.45
        ):
            lines.append([word])
        else:
            lines[-1].append(word)
    return [w for line in lines for w in sorted(line, key=lambda w: w["bbox"][0])]


def native_cell_text(characters, box):
    """Reconstruct geometric character order across separately drawn glyph runs."""
    selected = [
        c
        for c in characters
        if box[0] <= (c["bbox"][0] + c["bbox"][2]) / 2 < box[2]
        and box[1] <= (c["bbox"][1] + c["bbox"][3]) / 2 < box[3]
    ]
    if not selected:
        return ""
    # Remove an inferred space only when a separately drawn glyph occupies it.
    selected = [
        c
        for c in selected
        if not c["c"].isspace()
        or not any(
            not other["c"].isspace()
            and min(c["bbox"][2], other["bbox"][2])
            - max(c["bbox"][0], other["bbox"][0])
            > (c["bbox"][2] - c["bbox"][0]) * 0.6
            and abs(
                (c["bbox"][1] + c["bbox"][3] - other["bbox"][1] - other["bbox"][3]) / 2
            )
            < (c["bbox"][3] - c["bbox"][1]) * 0.5
            for other in selected
        )
    ]
    height = statistics.median(c["bbox"][3] - c["bbox"][1] for c in selected)
    lines = []
    for character in sorted(selected, key=lambda c: (c["bbox"][1] + c["bbox"][3]) / 2):
        center = (character["bbox"][1] + character["bbox"][3]) / 2
        if (
            not lines
            or center
            - statistics.mean((c["bbox"][1] + c["bbox"][3]) / 2 for c in lines[-1])
            > height * 0.5
        ):
            lines.append([character])
        else:
            lines[-1].append(character)
    output = []
    for line in lines:
        ordered = sorted(line, key=lambda c: c["bbox"][0])
        value = ""
        right = None
        for c in ordered:
            if (
                right is not None
                and c["bbox"][0] - right > height * 0.28
                and value
                and not value.endswith(" ")
                and c["c"] != " "
            ):
                value += " "
            value += c["c"]
            right = c["bbox"][2]
        output.append(text(value))
    return text(" ".join(output))


def grid_records(raw, boxes, page, method, make_record, *, bold_spans=()):
    """Recover explicit spans from native grid rectangles, not blank-cell fill."""
    xs = sorted(set(round(b[x], 2) for row in boxes for b in row if b for x in (0, 2)))
    ys = sorted(set(round(b[y], 2) for row in boxes for b in row if b for y in (1, 3)))
    cells = [[text(c) for c in row] for row in raw]
    inherited, spans = {}, {}
    for ri, row in enumerate(boxes):
        for ci, box in enumerate(row):
            if box is None or not cells[ri][ci]:
                continue
            covered_columns = [
                i
                for i in range(len(xs) - 1)
                if xs[i] >= box[0] - 0.5 and xs[i + 1] <= box[2] + 0.5
            ]
            covered_rows = [
                i
                for i in range(len(ys) - 1)
                if ys[i] >= box[1] - 0.5 and ys[i + 1] <= box[3] + 0.5
            ]
            if len(covered_columns) > 1 or len(covered_rows) > 1:
                spans.setdefault(ri, []).append(
                    {
                        "column": ci + 1,
                        "column_span": len(covered_columns),
                        "row_span": len(covered_rows),
                        "bbox": list(box),
                        "value": cells[ri][ci],
                    }
                )
            if len(covered_columns) == 1 and len(covered_rows) > 1:
                for target in covered_rows:
                    if (
                        target > ri
                        and target < len(cells)
                        and not cells[target][ci]
                        and boxes[target][ci] is None
                    ):
                        cells[target][ci] = cells[ri][ci]
                        inherited.setdefault(target, []).append(
                            {
                                "column": ci + 1,
                                "from_page": page,
                                "from_grid_row": ri + 1,
                                "bbox": list(box),
                                "value": cells[ri][ci],
                            }
                        )
    records = []
    for ri, row in enumerate(cells):
        if not any(row):
            continue
        available = [b for b in boxes[ri] if b]
        if not available:
            continue
        band = (
            [xs[0], ys[ri], xs[-1], ys[ri + 1]]
            if len(ys) == len(raw) + 1
            else [
                min(b[0] for b in available),
                min(b[1] for b in available),
                max(b[2] for b in available),
                max(b[3] for b in available),
            ]
        )
        record = make_record(row, page, band, method)
        if ri in spans:
            record["merged_cells"] = spans[ri]
        if ri in inherited:
            record["inherited_cells"] = inherited[ri]
        if ri < 4:
            chars = sum(
                count
                for box, count, bold in bold_spans
                if band[1] <= (box[1] + box[3]) / 2 < band[3]
                and band[0] <= (box[0] + box[2]) / 2 < band[2]
            )
            bold = sum(
                count
                for box, count, is_bold in bold_spans
                if is_bold
                and band[1] <= (box[1] + box[3]) / 2 < band[3]
                and band[0] <= (box[0] + box[2]) / 2 < band[2]
            )
            if chars:
                record["_header_hint"] = bold / chars >= 0.7
        records.append(record)
    return records


def prepare_fragment(fragment, is_header, numeric):
    """Flatten a bounded header block and keep its hierarchy and source labels."""
    rows = fragment["rows"]
    width = len(rows[0]["cells"])
    depth = 0
    reference_rows = set()
    reference_index = next(
        (
            i
            for i, row in enumerate(rows[:6])
            if i > 0
            and all(
                re.fullmatch(r"\(\s*" + str(c + 1) + r"\s*\)", text(value))
                for c, value in enumerate(row["cells"])
            )
        ),
        None,
    )
    grid_header_end = None
    if rows[0]["method"].startswith("OCR") and not rows[0].get("_header_hint"):
        for i, row in enumerate(rows[1:6], 1):
            filled = [c for c in row["cells"] if text(c)]
            if filled and sum(numeric(c) is not None for c in filled) >= max(
                2, len(filled) * 0.4
            ):
                preceding = rows[:i]
                if all(
                    all(len(c.split()) <= 6 for c in r["cells"])
                    and sum(numeric(c) is not None for c in r["cells"])
                    < max(1, width * 0.4)
                    for r in preceding
                ):
                    grid_header_end = i
                break
    for index, row in enumerate(rows[:6]):
        values = [c for c in row["cells"] if text(c)]
        fraction = sum(numeric(c) is not None for c in values) / max(1, len(values))
        spanning = any(s["column_span"] > 1 for s in row.get("merged_cells", []))
        following = index + 1 < len(rows) and is_header(rows[index + 1]["cells"])
        known = is_header(row["cells"])
        hint = row.get("_header_hint", False)
        references = (
            index > 0
            and depth == index
            and all(
                re.fullmatch(r"\(\s*" + str(i + 1) + r"\s*\)", text(value))
                for i, value in enumerate(row["cells"])
            )
        )
        if references:
            reference_rows.add(index)
            depth = index + 1
            continue
        # Years can be spanning parents. Bold numeric business values alone
        # are not sufficient to remove a data row as a header.
        plausible = known or (hint and fraction < 0.4) or (spanning and following)
        if reference_index is not None and index < reference_index and fraction < 0.4:
            plausible = True
        if grid_header_end is not None and index < grid_header_end:
            plausible = True
        if index > 0 and "_header_hint" in row and not hint:
            previous_group = any(
                s["column_span"] > 1 for s in rows[index - 1].get("merged_cells", [])
            )
            plausible = known and previous_group
        if (
            index == 0
            and not plausible
            and len(rows) > 1
            and values
            and fraction < 0.25
        ):
            next_values = [c for c in rows[1]["cells"] if text(c)]
            plausible = (
                sum(numeric(c) is not None for c in next_values)
                / max(1, len(next_values))
                > 0.5
            )
        if not plausible:
            # A sparse unrecognized group above a recognized leaf is retained
            # as header context, with its explicit span if one is available.
            if index == 0 and following and len(values) <= max(2, width // 3):
                plausible = True
            else:
                break
        depth = index + 1
    for row in rows:
        row.pop("_header_hint", None)
    if not depth:
        return fragment
    header_rows = deepcopy(rows[:depth])
    paths = [[] for _ in range(width)]
    for header_index, row in enumerate(header_rows):
        if header_index in reference_rows:
            continue
        expanded = list(row["cells"])
        body_shared = {
            span["column"] - 1
            for span in row.get("merged_cells", [])
            if span["row_span"] > depth - header_index and span["column_span"] == 1
        }
        for span in row.get("merged_cells", []):
            for col in range(
                span["column"] - 1, min(width, span["column"] - 1 + span["column_span"])
            ):
                expanded[col] = span["value"]
        # A full-width document title has no column-specific meaning.
        if depth > 1 and len(set(filter(None, expanded))) == 1:
            continue
        for col, value in enumerate(expanded):
            if col in body_shared:
                continue
            value = text(value)
            if value and (not paths[col] or value != paths[col][-1]):
                paths[col].append(value)
    leaves = [p[-1] if p else "" for p in paths]
    duplicates = Counter(key(v) for v in leaves if v)
    spanning_parents = {
        s["value"]
        for r in header_rows
        for s in r.get("merged_cells", [])
        if s["column_span"] > 1
    }
    names = [
        " ".join(path)
        if duplicates[key(leaf)] > 1
        or (
            rows[0]["method"].startswith("OCR")
            and len(path) > 1
            and not any(p in spanning_parents for p in path[:-1])
        )
        else leaf
        for path, leaf in zip(paths, leaves)
    ]
    counts = Counter()
    for i, name in enumerate(names):
        name = name or f"Column {i + 1}"
        counts[name] += 1
        names[i] = name if counts[name] == 1 else f"{name} ({counts[name]})"
    header = deepcopy(header_rows[-1])
    header["cells"] = names
    header["bbox"] = [
        min(r["bbox"][0] for r in header_rows),
        min(r["bbox"][1] for r in header_rows),
        max(r["bbox"][2] for r in header_rows),
        max(r["bbox"][3] for r in header_rows),
    ]
    header.pop("merged_cells", None)
    header.pop("inherited_cells", None)
    fragment = {
        **fragment,
        "rows": [header] + rows[depth:],
        "has_header": True,
        "header_depth": depth,
        "header_ocr_disagreements": [
            {**item, "page": r["page"]}
            for r in header_rows
            for item in r.get("ocr_disagreements", [])
        ],
    }
    if depth > 1:
        fragment["header_paths"] = paths
        fragment["header_rows"] = [r["cells"] for r in header_rows]
    return fragment


def source_part(row):
    return {
        k: deepcopy(row[k]) for k in ("page", "bbox", "method", "confidence", "cells")
    }


def append_continuation(target, row):
    """Join description-only page-boundary fragments with both source parts.

    Restricting this to explicitly named descriptive columns avoids filling
    missing identifiers or amounts. The result always receives a review finding.
    """
    if not target["rows"]:
        return False
    previous = target["rows"][-1]
    if (
        previous["page"] >= row["page"]
        or row["page"] - max(s["page"] for s in previous.get("sources", [previous]))
        != 1
    ):
        return False
    descriptive = {
        i
        for i, h in enumerate(target["headers"])
        if key(h)
        in {"description", "details", "memo", "notes", "narration", "particulars"}
    }
    populated = {i for i, c in enumerate(row["cells"]) if text(c)}
    if not populated or not populated <= descriptive or len(populated) > 2:
        return False
    if not previous["cells"][0] or any(
        re.fullmatch(r"(?:grand\s+|sub\s*)?total", c, re.I)
        for c in previous["cells"][:3]
    ):
        return False
    if not all(previous["cells"][i] for i in populated):
        return False
    previous.setdefault("sources", [source_part(previous)]).append(source_part(row))
    for i in populated:
        previous["cells"][i] = text(previous["cells"][i] + " " + row["cells"][i])
    previous["confidence"] = min(previous["confidence"], row["confidence"])
    previous["continued_across_pages"] = True
    return True


def aligned_fragments(
    words,
    width,
    page,
    method,
    make_record,
    is_header,
    numeric,
    map_box=lambda b: b,
    recover_empty=None,
):
    """Use one header-anchored layout path for native text and OCR words.

    Close physical header lines are combined before choosing column anchors.
    Column starts, rather than nearest text starts, retain right-aligned values.
    """
    if not words:
        return []
    words = [
        w for w in words if not re.fullmatch(r"[.\u00b7\u2026]{3,}", w["text"].strip())
    ]
    if not words:
        return []
    height = statistics.median(w["bbox"][3] - w["bbox"][1] for w in words)
    unit = height / 13.5
    tolerance = max(2, height * 0.27)
    bands = []
    for word in sorted(words, key=lambda w: (w["bbox"][1] + w["bbox"][3]) / 2):
        center = (word["bbox"][1] + word["bbox"][3]) / 2
        if (
            not bands
            or center
            - statistics.mean((w["bbox"][1] + w["bbox"][3]) / 2 for w in bands[-1])
            > tolerance
        ):
            bands.append([word])
        else:
            bands[-1].append(word)
    lines = [sorted(band, key=lambda w: w["bbox"][0]) for band in bands]
    centers = [
        statistics.mean((w["bbox"][1] + w["bbox"][3]) / 2 for w in line)
        for line in lines
    ]

    def groups(line):
        result = []
        for word in line:
            gap = word["bbox"][0] - result[-1][-1]["bbox"][2] if result else 0
            separate_caps = (
                bool(result)
                and word["text"].isupper()
                and result[-1][-1]["text"].isupper()
                and gap > height * 0.65
            )
            if not result or separate_caps or gap > max(13 * unit, height * 1.05):
                result.append([word])
            else:
                result[-1].append(word)
        return result

    def box(line):
        return [
            min(w["bbox"][0] for w in line),
            min(w["bbox"][1] for w in line),
            max(w["bbox"][2] for w in line),
            max(w["bbox"][3] for w in line),
        ]

    indices = [
        i
        for i, line in enumerate(lines)
        if is_header([w["text"] for w in line]) and len(groups(line)) >= 2
    ]
    generic = set()
    if not indices:
        # Unknown labels need repeated numeric body rows aligned to the same
        # widely spaced columns; prose and a single number are insufficient.
        for i, line in enumerate(lines):
            anchor = groups(line)
            if len(anchor) < 3 or any(numeric(w["text"]) is not None for w in line):
                continue
            starts = [g[0]["bbox"][0] for g in anchor]
            bounds = (
                [starts[0] - 6 * unit] + [x - 4 * unit for x in starts[1:]] + [width]
            )
            supported = 0
            for j in range(i + 1, min(len(lines), i + 13)):
                if centers[j] - centers[i] > height * 16:
                    break
                filled = set()
                digits = 0
                for word in lines[j]:
                    col = next(
                        (
                            c
                            for c in range(len(starts))
                            if bounds[c] <= word["bbox"][0] < bounds[c + 1]
                        ),
                        None,
                    )
                    if col is not None:
                        filled.add(col)
                        digits += numeric(word["text"]) is not None
                if digits and len(filled) >= max(3, len(starts) * 0.6):
                    supported += 1
            if supported >= 2:
                indices.append(i)
                generic.add(i)
    if indices and any(w.get("bold") for w in lines[indices[0]]):
        indices = [i for i in indices if any(w.get("bold") for w in lines[i])]
    used = set()
    out = []
    suffixes = {
        "id",
        "no",
        "number",
        "price",
        "amount",
        "rate",
        "code",
        "date",
        "value",
        "qty",
        "name",
        "usd",
        "eur",
        "inr",
        "total",
        "%",
    }
    for start in indices:
        if start in used:
            continue
        header_end = start + 1
        while header_end < len(lines) and header_end - start < 5:
            line = lines[header_end]
            labels = [w["text"] for w in line]
            gap = centers[header_end] - centers[header_end - 1]
            short_suffix = all(text(v).lower() in suffixes for v in labels)
            generic_suffix = (
                start in generic
                and len(line) <= len(lines[start])
                and all(len(v) <= 16 for v in labels)
            )
            if (
                gap
                <= height
                * (
                    2.5
                    if is_header(labels)
                    and len(groups(line)) > len(groups(lines[header_end - 1]))
                    else 1.5
                )
                and (is_header(labels) or short_suffix or generic_suffix)
                and not any(numeric(v) is not None for v in labels)
            ):
                header_end += 1
            else:
                break
        used.update(range(start, header_end))
        anchor_index = max(
            range(start, header_end), key=lambda i: len(groups(lines[i]))
        )
        anchor = groups(lines[anchor_index])
        starts = [g[0]["bbox"][0] for g in anchor]
        bounds = [starts[0] - 6 * unit] + [x - 4 * unit for x in starts[1:]] + [width]
        names = [" ".join(w["text"] for w in g) for g in anchor]
        for li in range(anchor_index + 1, header_end):
            for w in lines[li]:
                col = next(
                    (
                        i
                        for i in range(len(starts))
                        if bounds[i] <= w["bbox"][0] < bounds[i + 1]
                    ),
                    None,
                )
                if col is not None:
                    names[col] = text(names[col] + " " + w["text"])
        header_words = [w for line in lines[start:header_end] for w in line]
        header = make_record(
            names,
            page,
            map_box(box(header_words)),
            method,
            min(w.get("score", 1.0) for w in header_words),
        )
        header["_header_hint"] = True
        records = [header]
        end = next(
            (i for i in indices if i >= header_end and i not in used), len(lines)
        )
        previous = centers[header_end - 1]
        for li in range(header_end, end):
            if centers[li] - previous > max(42 * unit, height * 3.2):
                break
            line = lines[li]
            cells = [""] * len(starts)
            scores = []
            for word in line:
                col = next(
                    (
                        i
                        for i in range(len(starts))
                        if bounds[i] <= word["bbox"][0] < bounds[i + 1]
                    ),
                    None,
                )
                if col is not None:
                    cells[col] = text(cells[col] + " " + word["text"])
                    scores.append(word.get("score", 1.0))
            if not any(cells):
                continue
            retries = []
            if recover_empty:
                line_box = box(line)
                for col, value in enumerate(cells):
                    if value:
                        continue
                    recovered = recover_empty(
                        [
                            bounds[col],
                            line_box[1] - 3 * unit,
                            bounds[col + 1],
                            line_box[3] + 3 * unit,
                        ]
                    )
                    if recovered:
                        cells[col] = recovered["text"]
                        scores.append(recovered["score"])
                        retries.append(
                            {
                                "column": col + 1,
                                "route": "recognition-only consensus",
                                "score": recovered["score"],
                            }
                        )
            descriptive = {
                i
                for i, h in enumerate(names)
                if key(h)
                in {
                    "description",
                    "notes",
                    "memo",
                    "details",
                    "narration",
                    "particulars",
                }
            }
            populated = {i for i, c in enumerate(cells) if c}
            if (
                len(records) > 1
                and populated <= descriptive
                and centers[li] - previous < height * 1.55
            ):
                for col in populated:
                    records[-1]["cells"][col] = text(
                        records[-1]["cells"][col] + " " + cells[col]
                    )
                old = records[-1]["bbox"]
                new = map_box(box(line))
                records[-1]["bbox"] = [
                    min(old[0], new[0]),
                    min(old[1], new[1]),
                    max(old[2], new[2]),
                    max(old[3], new[3]),
                ]
            else:
                records.append(
                    make_record(
                        cells,
                        page,
                        map_box(box(line)),
                        method,
                        min(scores) if scores else 0,
                    )
                )
                if retries:
                    records[-1]["ocr_retries"] = retries
                records[-1]["_header_hint"] = False
            previous = centers[li]
        if len(records) > 1:
            fragment = {
                "rows": records,
                "bbox": map_box(
                    [
                        starts[0] - 6 * unit,
                        box(header_words)[1],
                        max(w["bbox"][2] for r in lines[header_end:end] for w in r)
                        if header_end < end
                        else width,
                        box(lines[min(end - 1, len(lines) - 1)])[3],
                    ]
                ),
                "width": width,
            }
            out.append(fragment)
    return out
