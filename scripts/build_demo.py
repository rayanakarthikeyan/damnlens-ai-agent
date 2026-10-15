"""Caption the actual browser-session recording. Never substitute still images.

The raw recording and its edit timeline are included so the submitted movie can
be rebuilt. Only idle gaps between steps and a static download pause were cut;
the captured extraction footage is played at its original speed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "docs/recordings/damnlens-app-session.mp4"
OUTPUT = ROOT / "docs/damnlens-demo.mp4"
TMP = ROOT / "tmp/live-demo"
TIMELINE = json.loads((ROOT / "docs/demo-timeline.json").read_text(encoding="utf-8"))
DURATION = TIMELINE["duration_seconds"]


def timestamp(seconds, srt=False, ass=False):
    millis = round(seconds * 1000)
    minutes, remainder = divmod(millis, 60000)
    second, fraction = divmod(remainder, 1000)
    if ass:
        centis = round(seconds * 100)
        minute, rem = divmod(centis, 6000)
        sec, centi = divmod(rem, 100)
        return f"0:{minute:02}:{sec:02}.{centi:02}"
    if srt:
        return f"00:{minutes:02}:{second:02},{fraction:03}"
    return f"{minutes:02}:{second:02}"


def font():
    for path in [
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        if Path(path).exists():
            return ImageFont.truetype(path, 34)
    raise RuntimeError("Install Segoe UI, DejaVu Sans or Helvetica for captions")


def wrap(text):
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    face = font()
    lines, current = [], ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=face) > 1760:
            lines.append(current)
            current = word
        else:
            current = trial
    lines.append(current)
    if len(lines) > 2:
        raise ValueError(f"Caption exceeds two lines: {text}")
    return lines


def captions():
    TMP.mkdir(parents=True, exist_ok=True)
    ass = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1920",
        "PlayResY: 1080",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Segoe UI,34,&H00FFFFFF,&H00FFFFFF,&H0020120B,&H0020120B,0,0,0,0,100,100,0,0,1,0,0,2,80,80,29,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    srt, chapters, rows = [], [], []
    for index, clip in enumerate(TIMELINE["clips"]):
        start = clip["start"]
        end = DURATION if index == len(TIMELINE["clips"]) - 1 else clip["end"]
        if not (0 <= start < end <= DURATION):
            raise ValueError("Invalid caption timing")
        text = clip["caption"]
        wrapped = wrap(text)
        ass_text = r"\N".join(wrapped)
        ass.append(
            f"Dialogue: 0,{timestamp(start, ass=True)},{timestamp(end, ass=True)},Default,,0,0,0,,{ass_text}"
        )
        srt.append(
            f"{index + 1}\n{timestamp(start, srt=True)} --> {timestamp(end, srt=True)}\n"
            + "\n".join(wrapped)
            + "\n"
        )
        title = clip["name"].replace("-", " ").capitalize()
        chapters.append(f"{timestamp(start)} {title}")
        rows.append(f"| {timestamp(start)}–{timestamp(end)} | {title} | {text} |")
    (TMP / "captions.ass").write_text("\n".join(ass) + "\n", encoding="utf-8")
    (ROOT / "docs/recordings/damnlens-demo.srt").write_text(
        "\n".join(srt), encoding="utf-8"
    )
    (ROOT / "docs/demo-chapters.txt").write_text(
        "\n".join(chapters) + "\n", encoding="utf-8"
    )
    (ROOT / "docs/DEMO_SCRIPT.md").write_text(
        "# DamnLens AI Agent application demonstration\n\n"
        f"**{timestamp(DURATION)}. Application screen recording with captions and no audio.**\n\n"
        "The video records operating the working browser application: PDF selection and extraction, source inspection, local scanned OCR, an image result, 50-page processing, complex headers and source parts, validation, an explicit correction, review and an actual Excel download. "
        "It uses timestamped browser frames captured during those operations, rather than the earlier screenshot presentation. "
        "Idle gaps between steps and one static download pause are removed. Extraction footage is not accelerated. The original browser capture is 1265 × 712 with a variable sampling rate; the final 1920 × 1080 movie encodes at 24 fps. "
        "Captions sit below the app. No scoring, production banners, sidebars, counters or timers are added.\n\n"
        "All documents are fictional fixtures. The currency correction is an explicit demonstration edit, preserved in the history; source total and balance errors remain acknowledged findings. "
        "The Gemini section demonstrates configuration and request limits only. No new cloud request is made or represented as completed. "
        "The final accuracy screen is the saved development-sample benchmark, not a new hidden-document evaluation.\n\n"
        "| Time | Operation | Caption |\n|---|---|---|\n"
        + "\n".join(rows)
        + "\n\n## Rebuild and evidence\n\n"
        "Run `python scripts/build_demo.py` after installing `requirements-dev.txt`. "
        "The builder captions `recordings/damnlens-app-session.mp4` using `demo-timeline.json`; it never falls back to still screenshots. "
        "Use `--verify-only` to check an existing movie. Optional subtitles are in `recordings/damnlens-demo.srt`, separate from the final movie to prevent duplicate automatic subtitles. "
        "`recordings/capture-manifest.json` retains source-frame hashes and timestamps. "
        "`../reports/demo-verification.json` records media checks; `../reports/demo-live-check.json` verifies the actual demonstrated results and downloaded workbook.\n",
        encoding="utf-8",
    )


def verify(ffmpeg):
    probe = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(OUTPUT)], capture_output=True, text=True
    )
    metadata = probe.stderr
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", metadata)
    if match is None:
        raise ValueError("Cannot read movie duration")
    duration = int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])
    if (
        abs(duration - DURATION) > 0.05
        or not 120 <= duration <= 240
        or "Audio:" in metadata
    ):
        raise ValueError("Check the four-minute limit, timeline and absence of audio")
    if (
        "Video: h264" not in metadata
        or "1920x1080" not in metadata
        or "24 fps" not in metadata
    ):
        raise ValueError("Movie must be full-HD H.264 at 24 fps")
    subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(OUTPUT), "-f", "null", "-"], check=True
    )
    manifest = json.loads((ROOT / "docs/recordings/capture-manifest.json").read_text())
    report = {
        "file": "docs/damnlens-demo.mp4",
        "seconds": duration,
        "resolution": [1920, 1080],
        "codec": "H.264",
        "pixel_format": "yuv420p",
        "fps": 24,
        "audio_streams": 0,
        "full_decode": "passed",
        "recorded_clips": len(TIMELINE["clips"]),
        "captured_browser_frames": len(manifest["frames"]),
        "source_capture_resolution": manifest["native_resolution"],
        "capture_method": "Timestamped browser frames captured while operating the working application",
        "editing": TIMELINE["editing"],
        "gemini_scope": TIMELINE["gemini"],
        "burned_in_captions": True,
        "caption_font_pixels": 34,
        "max_caption_lines": 2,
        "presentation": "App screen and captions only; no added scores or production overlays.",
        "bytes": OUTPUT.stat().st_size,
        "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "raw_recording_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
    }
    (ROOT / "reports/demo-verification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    if not RAW.is_file():
        raise FileNotFoundError(
            "The actual browser recording is required; screenshots are not a substitute"
        )
    if not args.verify_only:
        captions()
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "warning",
                "-y",
                "-i",
                str(RAW),
                "-t",
                str(DURATION),
                "-vf",
                "scale=1920:944:force_original_aspect_ratio=decrease:in_range=pc:out_range=tv,setsar=1,pad=1920:1080:(ow-iw)/2:0:color=0x0b1220,ass=tmp/live-demo/captions.ass,format=yuv420p,fps=24",
                "-an",
                "-r",
                "24",
                "-fps_mode",
                "cfr",
                "-pix_fmt",
                "yuv420p",
                "-color_range",
                "tv",
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
            cwd=ROOT,
        )
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                "1",
                "-i",
                str(OUTPUT),
                "-frames:v",
                "1",
                str(ROOT / "docs/damnlens-demo-poster.jpg"),
            ],
            check=True,
        )
    report = verify(ffmpeg)
    print(
        f"Verified actual app recording: {timestamp(DURATION)}, no audio, {report['captured_browser_frames']} captured frames",
        flush=True,
    )


if __name__ == "__main__":
    main()
