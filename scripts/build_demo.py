"""Build the submission demo from original Chrome window recordings.

Cuts remove idle navigation. Retained footage stays at recorded speed, without
voice, captions, generated screenshots, synthetic cursor movement or scores.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUTPUT = DOCS / "damnlens-demo.mp4"
WORK = ROOT / "tmp/screen-recording/build"


def timestamp(seconds):
    minutes, remainder = divmod(int(seconds), 60)
    return f"{minutes:02}:{remainder:02}"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(ffmpeg, *args, capture=False):
    return subprocess.run(
        [ffmpeg, "-hide_banner", *map(str, args)],
        check=True,
        capture_output=capture,
        text=capture,
    )


def decode(ffmpeg, path):
    result = run(
        ffmpeg,
        "-v",
        "error",
        "-i",
        path,
        "-progress",
        "pipe:1",
        "-f",
        "null",
        "-",
        capture=True,
    )
    times = re.findall(r"out_time_us=(\d+)", result.stdout)
    if not times or "progress=end" not in result.stdout:
        raise ValueError(f"Incomplete video decode: {path.name}")
    return int(times[-1]) / 1_000_000


def metadata(ffmpeg, path):
    # An input-only probe intentionally exits nonzero: there is no output.
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True
    )
    if "Video:" not in result.stderr:
        raise ValueError(f"No video stream: {path.name}")
    return result.stderr


def timeline():
    data = json.loads((DOCS / "demo-timeline.json").read_text(encoding="utf-8"))
    position = 0
    for clip in data["clips"]:
        duration = clip["source_end"] - clip["source_start"]
        source = (DOCS / clip["source"]).resolve()
        if not source.is_relative_to((DOCS / "recordings").resolve()):
            raise ValueError("A source must be inside docs/recordings")
        if not source.is_file() or source.suffix != ".webm":
            raise ValueError("Original screen recordings are required")
        if clip["source_start"] < 0 or duration <= 0:
            raise ValueError("Invalid source cut")
        if clip["start"] != position or clip["end"] != position + duration:
            raise ValueError("Output timeline has a gap or overlap")
        position += duration
    if position != data["duration_seconds"] or not 120 <= position <= 240:
        raise ValueError("Submission recording must last two to four minutes")
    return data


def chapters(data):
    groups = [
        (0, "Digital PDF and source evidence"),
        (5, "Scanned PDF and local OCR"),
        (8, "50-page extraction and integrity"),
        (11, "Nested headers and merged cells"),
        (13, "Validation and review"),
        (22, "Reviewed Excel download"),
    ]
    lines, readable = [";FFMETADATA1", "title=DamnLens AI Agent"], []
    for index, (clip_index, title) in enumerate(groups):
        start = data["clips"][clip_index]["start"]
        end = (
            data["clips"][groups[index + 1][0]]["start"]
            if index + 1 < len(groups)
            else data["duration_seconds"]
        )
        lines.extend(
            [
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={start * 1000}",
                f"END={end * 1000}",
                f"title={title}",
            ]
        )
        readable.append(f"{timestamp(start)} {title}")
    (DOCS / "demo-chapters.txt").write_text(
        "\n".join(readable) + "\n", encoding="utf-8"
    )
    path = WORK / "chapters.ffmeta"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def build(ffmpeg, data):
    WORK.mkdir(parents=True, exist_ok=True)
    parts = []
    for index, clip in enumerate(data["clips"]):
        part = WORK / f"clip-{index:02}.mp4"
        print(f"Rendering {index + 1}/{len(data['clips'])}: {clip['name']}", flush=True)
        # Decode before seeking: MediaRecorder WebM may have no seek cues.
        # Input-side fast seeking can return an incorrect source frame.
        run(
            ffmpeg,
            "-loglevel",
            "error",
            "-y",
            "-i",
            DOCS / clip["source"],
            "-ss",
            clip["source_start"],
            "-t",
            clip["source_end"] - clip["source_start"],
            "-vf",
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x101827,setsar=1,fps=30,format=yuv420p",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-threads",
            "4",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            part,
        )
        parts.append(f"file '{part.as_posix()}'")
    cuts = WORK / "concat.txt"
    cuts.write_text("\n".join(parts) + "\n", encoding="utf-8")
    chapter_file = chapters(data)
    pending = WORK / "damnlens-demo.mp4"
    run(
        ffmpeg,
        "-loglevel",
        "error",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        cuts,
        "-i",
        chapter_file,
        "-map",
        "0:v:0",
        "-map_metadata",
        "1",
        "-map_chapters",
        "1",
        "-c:v",
        "copy",
        "-an",
        "-movflags",
        "+faststart",
        pending,
    )
    decode(ffmpeg, pending)
    OUTPUT.write_bytes(pending.read_bytes())
    run(
        ffmpeg,
        "-loglevel",
        "error",
        "-y",
        "-i",
        OUTPUT,
        "-ss",
        "25",
        "-frames:v",
        "1",
        DOCS / "damnlens-demo-poster.jpg",
    )


def verify(ffmpeg, data):
    details = metadata(ffmpeg, OUTPUT)
    duration = decode(ffmpeg, OUTPUT)
    if "Audio:" in details or "Video: h264" not in details:
        raise ValueError("Expected H.264 video without audio")
    if "1920x1080" not in details or "30 fps" not in details:
        raise ValueError("Expected full-HD video at 30 fps")
    if abs(duration - data["duration_seconds"]) > 0.2:
        raise ValueError("Final duration differs from edit timeline")
    sources = []
    for relative in sorted({clip["source"] for clip in data["clips"]}):
        path = DOCS / relative
        source_duration = decode(ffmpeg, path)
        if any(
            c["source_end"] > source_duration
            for c in data["clips"]
            if c["source"] == relative
        ):
            raise ValueError("A cut exceeds its original recording")
        if "Audio:" in metadata(ffmpeg, path):
            raise ValueError("Unexpected audio in an original recording")
        sources.append(
            dict(
                file=f"docs/{relative}",
                seconds=source_duration,
                bytes=path.stat().st_size,
                sha256=digest(path),
                full_decode="passed",
            )
        )
    manifest = dict(
        capture=data["capture_method"],
        sources=sources,
        editing=data["editing"],
        timeline="docs/demo-timeline.json",
    )
    (DOCS / "recordings/capture-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    report = dict(
        file="docs/damnlens-demo.mp4",
        seconds=duration,
        resolution=[1920, 1080],
        codec="H.264",
        pixel_format="yuv420p",
        fps=30,
        audio_streams=0,
        full_decode="passed",
        recorded_clips=len(data["clips"]),
        original_recordings=len(sources),
        capture_method=data["capture_method"],
        editing=data["editing"],
        burned_in_captions=False,
        synthetic_frames=False,
        synthetic_cursor=False,
        gemini_scope=data["gemini"],
        correction_scope=data["correction_scope"],
        bytes=OUTPUT.stat().st_size,
        sha256=digest(OUTPUT),
        sources=sources,
    )
    (ROOT / "reports/demo-verification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    data = timeline()
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    if not args.verify_only:
        build(ffmpeg, data)
    report = verify(ffmpeg, data)
    print(
        f"Verified {timestamp(report['seconds'])} live app video; no audio or captions.",
        flush=True,
    )


if __name__ == "__main__":
    main()
