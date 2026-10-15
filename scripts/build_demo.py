"""Build a silent 232-second submission edit from authentic application captures.

Captions and editorial close-ups explain evidence; no app output is fabricated.
Use --frames-only to review the edit or --verify-only to check an existing movie.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp/demo"
SHOTS = ROOT / "docs/screenshots"
OUTPUT = ROOT / "docs/damnlens-demo.mp4"
SCENES = json.loads((ROOT / "docs/demo-storyboard.json").read_text(encoding="utf-8"))
DURATION = sum(scene["seconds"] for scene in SCENES)
FPS = 24


def font(size, bold=False):
    candidates = [
        Path("C:/Windows/Fonts") / ("segoeuib.ttf" if bold else "segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu")
        / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Helvetica.ttc"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    raise RuntimeError(
        "Install Segoe UI, DejaVu Sans or Helvetica for legible captions"
    )


def lines(draw, text, face, width):
    result, current = [], ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=face) > width:
            if not current:
                raise ValueError(f"Word does not fit: {word}")
            result.append(current)
            current = word
        else:
            current = trial
    if current:
        result.append(current)
    return result


def block(draw, text, xy, face, width, color, max_lines, gap=8):
    content = lines(draw, text, face, width)
    if len(content) > max_lines:
        raise ValueError(f"Text overflows its allocated area: {text}")
    x, y = xy
    for line in content:
        draw.text((x, y), line, font=face, fill=color)
        y += face.size + gap


def timestamp(seconds, srt=False):
    minutes, second = divmod(seconds, 60)
    return f"00:{minutes:02}:{second:02},000" if srt else f"{minutes:02}:{second:02}"


def frame(scene, number, crop, elapsed):
    canvas = Image.new("RGB", (1920, 1080), "#0b1220")
    draw = ImageDraw.Draw(canvas)
    draw.text((48, 22), "DAMNLENS AI AGENT", font=font(19, True), fill="#83dccc")
    draw.text(
        (1488, 22),
        f"{number + 1:02} / {len(SCENES)}   •   SILENT DEMO",
        font=font(18),
        fill="#b7c5dc",
    )
    block(draw, scene["title"], (48, 61), font(43, True), 1810, "#f5f8ff", 1)
    draw.line((48, 130, 1872, 130), fill="#273751", width=1)
    with Image.open(SHOTS / scene["image"]) as original:
        shot = original.convert("RGB")
    if crop is not None:
        if not (
            0 <= crop[0] < crop[2] <= shot.width
            and 0 <= crop[1] < crop[3] <= shot.height
        ):
            raise ValueError(f"Crop exceeds authentic capture: {scene['image']} {crop}")
        shot = shot.crop(crop)
    stage_width = 1824 if scene.get("wide") else 1400
    shot = ImageOps.contain(shot, (stage_width, 730), Image.Resampling.LANCZOS)
    draw.rounded_rectangle(
        (46, 157, 50 + stage_width, 891), 13, fill="#111e32", outline="#304460", width=2
    )
    canvas.paste(
        shot, (48 + (stage_width - shot.width) // 2, 159 + (730 - shot.height) // 2)
    )
    if scene.get("wide"):
        block(
            draw,
            "EXPORTED XLSX / TABLE 1 / A1:L12 / 12 DATA COLUMNS",
            (76, 179),
            font(20, True),
            1720,
            "#83dccc",
            1,
        )
    else:
        sidebar(draw, scene)
    draw.rectangle((48, 918, 1872, 920), fill="#304460")
    caption_lines = lines(draw, scene["caption"], font(31), 1760)
    if len(caption_lines) > 2:
        raise ValueError(f"Caption exceeds two lines: {scene['caption']}")
    for index, line in enumerate(caption_lines):
        x = (1920 - draw.textlength(line, font=font(31))) / 2
        draw.text((x, 938 + 42 * index), line, font=font(31), fill="#f4f7ff")
    footer = "Real screens • Edited close-ups and timing • Development evidence"
    if number == len(SCENES) - 1:
        footer = "github.com/rayanakarthikeyan/damnlens-ai-agent"
    draw.text((48, 1041), footer, font=font(16), fill="#9db0cc")
    draw.text(
        (1718, 1041),
        f"{timestamp(elapsed)} / {timestamp(DURATION)}",
        font=font(17),
        fill="#b7c5dc",
    )
    draw.rectangle((0, 1074, 1919, 1079), fill="#263750")
    draw.rectangle(
        (0, 1074, max(1, int(1920 * elapsed / DURATION)), 1079), fill="#75d7c3"
    )
    return canvas


def sidebar(draw, scene):
    block(draw, "JUDGING FOCUS", (1488, 162), font(17, True), 380, "#83dccc", 1)
    block(draw, scene["category"], (1488, 197), font(23, True), 380, "#e5edfb", 3)
    for index, (value, label) in enumerate(scene["facts"]):
        y = 335 + 157 * index
        draw.line((1488, y - 17, 1872, y - 17), fill="#273751", width=1)
        block(draw, value, (1488, y), font(34, True), 380, "#ffffff", 1)
        block(draw, label, (1488, y + 51), font(23), 380, "#c4d2e8", 2)
    block(
        draw,
        scene.get("media", "APPLICATION CAPTURE"),
        (1488, 841),
        font(15, True),
        380,
        "#8fa5c4",
        2,
        gap=3,
    )


def storyboard():
    TMP.mkdir(parents=True, exist_ok=True)
    entries, subtitles, chapters, script = [], [], [], []
    elapsed = 0
    for index, scene in enumerate(SCENES):
        crops = scene.get("crops", [None])
        for part, crop in enumerate(crops):
            path = TMP / f"submission-{index:02}-{part}.png"
            frame(scene, index, crop, elapsed).save(path)
            entries.append((path, scene["seconds"] / len(crops)))
        end = elapsed + scene["seconds"]
        subtitles.append(
            f"{index + 1}\n{timestamp(elapsed, True)} --> {timestamp(end, True)}\n{scene['caption']}\n"
        )
        chapters.append(f"{timestamp(elapsed)} {scene['title']}")
        script.append(
            f"| {timestamp(elapsed)}–{timestamp(end)} | {scene['title']} | {scene['caption']} |"
        )
        elapsed = end
    if DURATION != 232 or DURATION > 240:
        raise ValueError(f"Demo must stay within four minutes: {DURATION}")
    (ROOT / "docs/damnlens-demo.srt").write_text("\n".join(subtitles), encoding="utf-8")
    (ROOT / "docs/demo-chapters.txt").write_text(
        "\n".join(chapters) + "\n", encoding="utf-8"
    )
    (ROOT / "docs/DEMO_SCRIPT.md").write_text(
        "# DamnLens AI Agent submission demo\n\n"
        "**3 minutes 52 seconds. 1920 × 1080. Captions only; no audio.**\n\n"
        "This edited walkthrough uses authentic browser captures, a read-only render of the actual exported XLSX, and the published CI run. "
        "Close-ups and display times are editorial; this is not an uncut speed recording. "
        "All application examples use fictional data. Gemini screens show the recorded live test; making the video sent no new cloud requests.\n\n"
        "The five rubric labels show **available marks**, not marks awarded. "
        "The closing case for the project is traceability, explicit uncertainty, optional independent AI checking and reproducibility. "
        "No win or hidden-PDF accuracy is claimed.\n\n"
        "| Time | Screen / requirement | Burned-in caption |\n|---|---|---|\n"
        + "\n".join(script)
        + "\n\n## Submission files\n\n"
        "- `damnlens-demo.mp4`: ready-to-submit video with captions burned in.\n"
        "- `damnlens-demo.srt`: matching optional subtitles; captions are already visible in the movie.\n"
        "- `demo-chapters.txt`: chapter timestamps.\n"
        "- `demo-storyboard.json`: edit specification with original capture crops.\n"
        "- `../reports/demo-verification.json`: codec, duration, silent-stream check, full decode, hashes and source-capture manifest.\n"
        "- `../reports/demo-extraction-check.json`: fresh 50-page and PNG checks.\n\n"
        "## Rebuild\n\n"
        "Install `requirements-dev.txt`, then run `python scripts/build_demo.py`. "
        "Use `--frames-only` to inspect before encoding, or `--verify-only` to verify an existing movie. "
        "The XLSX image is a read-only render of `samples/converted/01_invoice_register.xlsx`, `Table 1`, A1:L12, without changes to values or formatting.\n\n"
        "## Evidence scope\n\n"
        "The 50-page fixture repeats the first invoice page 50 times to test boundary handling and duplicate preservation; it is not a 50-layout diversity test. "
        "The PNG is inventory page one rasterized at 180 DPI. The 864-cell sample, 16-case complex and 15-case varied cohorts are separate development results. "
        "Expanded 10/11 checks include selected checkpoints rather than complete transcription of every public document; one ambiguous header remains flagged. "
        "The small live Gemini cohort covers three dummy first pages (360 cells, 36 headers), with two earlier provider failures disclosed. "
        "See the accuracy, expanded evaluation and Gemini reports for comparison policies. "
        "The CI screen shows source commit `c8d8b2b`, [run 38715554376](https://github.com/rayanakarthikeyan/damnlens-ai-agent/actions/runs/38715554376).\n",
        encoding="utf-8",
    )
    return entries


def verify(ffmpeg):
    probe = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(OUTPUT)], capture_output=True, text=True
    )
    metadata = probe.stderr
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", metadata)
    if match is None:
        raise ValueError("Cannot read movie duration")
    duration = int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])
    if duration != DURATION or "Audio:" in metadata:
        raise ValueError(
            "Movie must be exactly 232 seconds and contain no audio stream"
        )
    if (
        "Video: h264" not in metadata
        or "1920x1080" not in metadata
        or "24 fps" not in metadata
    ):
        raise ValueError("Movie must be full-HD H.264 at 24 fps")
    subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(OUTPUT), "-f", "null", "-"], check=True
    )
    report = {
        "file": "docs/damnlens-demo.mp4",
        "seconds": duration,
        "resolution": [1920, 1080],
        "codec": "H.264",
        "pixel_format": "yuv420p",
        "fps": FPS,
        "audio_streams": 0,
        "full_decode": "passed",
        "scenes": len(SCENES),
        "burned_in_captions": True,
        "caption_font_pixels": 31,
        "max_caption_lines": 2,
        "layout_overflow_checks": "passed",
        "bytes": OUTPUT.stat().st_size,
        "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "editing": "Authentic captures with editorial crops, captions and timing; not real-time performance footage.",
        "capture_sources": [
            {
                "file": f"docs/screenshots/{s['image']}",
                "seconds": s["seconds"],
                "title": s["title"],
                "sha256": hashlib.sha256((SHOTS / s["image"]).read_bytes()).hexdigest(),
            }
            for s in SCENES
        ],
    }
    (ROOT / "reports/demo-verification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames-only", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    if not args.verify_only:
        entries = storyboard()
        print(
            f"Prepared {len(SCENES)} scenes, {len(entries)} close-ups, {DURATION} seconds",
            flush=True,
        )
        if args.frames_only:
            return
        sequence = TMP / "submission-frames.txt"
        sequence.write_text(
            "".join(
                f"file '{path.as_posix()}'\nduration {seconds}\n"
                for path, seconds in entries
            )
            + f"file '{entries[-1][0].as_posix()}'\n",
            encoding="utf-8",
        )
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "warning",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(sequence),
                "-t",
                str(DURATION),
                "-vf",
                f"fps={FPS},format=yuv420p",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-movflags",
                "+faststart",
                str(OUTPUT),
            ],
            check=True,
        )
    report = verify(ffmpeg)
    print(
        f"Verified: {report['seconds']}s, 1080p H.264, no audio, {report['bytes']:,} bytes",
        flush=True,
    )


if __name__ == "__main__":
    main()
