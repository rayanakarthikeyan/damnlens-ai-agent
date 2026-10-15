"""Build a 150-second captioned walkthrough from real browser QA captures.

Not a real-time screen recording. Screenshots must be captured from the working
app; the script never fabricates UI output or measured extraction results.
"""

import json
import subprocess
import textwrap
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp" / "demo"
TMP.mkdir(parents=True, exist_ok=True)
SHOTS = ROOT / "docs" / "screenshots"
SCENES = [
    (
        "01-workspace-desktop.jpg",
        "Less paperwork. More possibility.",
        "A local AI workflow for documents",
        "Upload a PDF or image. LedgerLens inspects, extracts, stitches and validates the tables. Files stay on your computer. No cloud API key is required.",
    ),
    (
        "02-digital-extraction.jpg",
        "Three pages. One usable table.",
        "Native PDF extraction",
        "The invoice register has 12 columns across three pages. The agent preserves 31 rows, removes two repeated headers and keeps page provenance for every row.",
    ),
    (
        "03-source-evidence.jpg",
        "Every row has a source.",
        "Click to inspect the evidence",
        "Select an extracted row to highlight its original location, even after joining continuation pages. Verify figures against the page before using them.",
    ),
    (
        "04-agent-activity.jpg",
        "See what the agent did.",
        "A visible extraction lifecycle",
        "Inspect page routing and table fragments in the activity view. Native extraction falls back to OCR. Failed pages become explicit review findings. Duplicate business rows are preserved.",
    ),
    (
        "05-scanned-extraction.jpg",
        "Scans become spreadsheets.",
        "Local machine-learning OCR",
        "This inventory PDF contains images only. RapidOCR recognizes English text, OpenCV reconstructs the grid, and both pages are joined into one 20-row table.",
    ),
    (
        "06-validation.jpg",
        "Catch the details that matter.",
        "Validation with row references",
        "The bank fixture contains intentional mistakes. LedgerLens flags the wrong total, balance transitions, missing values and a sparse total row. Source errors remain visible.",
    ),
    (
        "07-cell-correction.jpg",
        "Review. Correct. Keep the history.",
        "Human oversight is part of the workflow",
        "Double-click a cell or press Enter to edit it. The original value is retained, the correction is timestamped, and validation reruns. No silent rewriting of source data.",
    ),
    (
        "08-reviewed-result.jpg",
        "Export the context, too.",
        "Excel, CSV and JSON",
        "Excel contains typed values, filters, frozen headers, validation findings, row evidence and correction history. Identifiers keep leading zeros. Document text is never executed as a spreadsheet formula.",
    ),
    (
        "09-accuracy-report.jpg",
        "Measured, not assumed.",
        "864 data cells compared with ground truth",
        "All three synthetic development fixtures match their ground truth. A separate 50-page test checks 501 rows. These results are reproducible, and are not a promise of hidden-test accuracy.",
    ),
    (
        "10-quick-guide.jpg",
        "Ready for a live demonstration.",
        "Built for the INCUXAI challenge 2026",
        "The submission includes source code, setup instructions, three original PDF and Excel pairs, measured reports, tests and this walkthrough. Practical limits and all libraries and models are credited.",
    ),
]


def font(size, bold=False, serif=False):
    base = Path("C:/Windows/Fonts")
    name = "georgia.ttf" if serif else "segoeuib.ttf" if bold else "segoeui.ttf"
    if (base / name).exists():
        return ImageFont.truetype(str(base / name), size)
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def wrapped(draw, text, xy, f, fill, width, line_gap=9):
    x, y = xy
    line = ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if draw.textlength(trial, font=f) > width and line:
            draw.text((x, y), line, font=f, fill=fill)
            y += f.size + line_gap
            line = word
        else:
            line = trial
    if line:
        draw.text((x, y), line, font=f, fill=fill)
        y += f.size + line_gap
    return y


def main():
    paths = []
    for i, (image, title, subtitle, body) in enumerate(SCENES):
        canvas = Image.new("RGB", (1920, 1080), "#f7f9f3")
        d = ImageDraw.Draw(canvas)
        d.rectangle((0, 0, 1920, 87), fill="#173c37")
        d.text((40, 23), "LedgerLens.", font=font(30, True), fill="#d6e9bb")
        d.text(
            (1275, 34),
            "INCUXAI 2026  /  APPLICATION WALKTHROUGH",
            font=font(15, True),
            fill="#afc4ba",
        )
        shot = Image.open(SHOTS / image).convert("RGB")
        shot.thumbnail((1330, 900), Image.Resampling.LANCZOS)
        x = 30 + (1330 - shot.width) // 2
        y = 112 + (900 - shot.height) // 2
        d.rounded_rectangle(
            (x - 1, y - 1, x + shot.width + 1, y + shot.height + 1),
            radius=8,
            fill="#e0e7d8",
        )
        canvas.paste(shot, (x, y))
        d.text((1400, 150), f"{i + 1:02d} / 10", font=font(18, True), fill="#95ab83")
        yy = wrapped(d, title, (1400, 205), font(45, serif=True), "#173c37", 470, 10)
        yy = wrapped(d, subtitle, (1400, yy + 26), font(20, True), "#6e8b59", 465, 9)
        wrapped(d, body, (1400, yy + 30), font(24), "#73846b", 465, 15)
        d.text(
            (40, 1039),
            "Captioned walkthrough of actual application screens. Editorial timing; not a real-time recording.",
            font=font(15),
            fill="#89967f",
        )
        d.rectangle((1400, 930, 1870, 935), fill="#e1e8d7")
        d.rectangle((1400, 930, 1400 + int(470 * (i + 1) / 10), 935), fill="#7c9d60")
        p = TMP / f"frame-{i:02d}.png"
        canvas.save(p)
        paths.append(p)
    sequence = TMP / "frames.txt"
    sequence.write_text(
        "".join(f"file '{p.as_posix()}'\nduration 15\n" for p in paths)
        + f"file '{paths[-1].as_posix()}'\n",
        encoding="utf-8",
    )
    out = ROOT / "docs" / "ledgerlens-demo.mp4"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(sequence),
            "-t",
            "150",
            "-vf",
            "fps=12,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "22",
            "-movflags",
            "+faststart",
            str(out),
        ],
        check=True,
    )
    probe = subprocess.run([ffmpeg, "-i", str(out)], capture_output=True, text=True)
    print(
        probe.stderr.split("Duration:")[1].splitlines()[0]
        if "Duration:" in probe.stderr
        else probe.stderr
    )
    print(out, out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
