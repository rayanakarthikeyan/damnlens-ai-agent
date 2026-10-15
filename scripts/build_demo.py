"""Build a 150-second captioned walkthrough from real browser QA captures.

Not a real-time screen recording. Screenshots must be captured from the working
app; the script never fabricates UI output or measured extraction results.
"""

import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp" / "demo"
TMP.mkdir(parents=True, exist_ok=True)
SHOTS = ROOT / "docs" / "screenshots"
SCENES = [
    (
        "30-workflow-selector.png",
        "Two AI workflows. Shared integrity.",
        "Local AI by default; optional Gemini second reading",
        "Local AI needs no key and has no API charges. Gemini-assisted AI independently reads selected difficult pages, within a request limit and after explicit cloud authorization. Both converge on source review and validated Excel.",
    ),
    (
        "02-digital-extraction.jpg",
        "Structured data with page coverage",
        "Inspect, extract, align and validate",
        "The invoice register has 12 columns across three pages. The agent preserves 31 rows, removes two repeated headers and keeps page provenance for every row.",
    ),
    (
        "20-cross-page-source-parts.jpg",
        "Two source parts. One logical row.",
        "Cross-page descriptions keep their evidence",
        "A description continues on page two. The agent retains six logical rows and all 12 columns. Part buttons show each original fragment. The reconstructed row remains flagged for source review.",
    ),
    (
        "19-resumed-run-log.jpg",
        "Resume verified completed pages",
        "Recovery is recorded in the agent log",
        "After interruption, Resume extraction reuses matching, checksum-verified pages. This run resumed page one and extracted page two. A changed source, mode, engine or model invalidates the checkpoint.",
    ),
    (
        "32-gemini-live-summary.png",
        "A live cloud second reading",
        "Bounded usage, independent candidates and explicit coverage",
        "Local OCR joins all 20 inventory rows. Gemini reads the first scanned page as a PNG and matches 120 checked cells and 12 headers. The one-request limit skips page two. Earlier HTTP 503 failures remain in the report; local data stayed available.",
    ),
    (
        "06-validation.jpg",
        "Catch the details that matter.",
        "Validation with row references",
        "The bank fixture contains intentional mistakes. DamnLens AI Agent flags the wrong total, balance transitions, missing values and a sparse total row. Source errors remain visible.",
    ),
    (
        "07-review-checkpoint.jpg",
        "An explicit review checkpoint",
        "Source verification and acknowledged findings",
        "A completed extraction is a draft. Completing review confirms source checks and records a note for outstanding findings. Subsequent corrections invalidate that review and preserve its previous decision.",
    ),
    (
        "08-reviewed-export.jpg",
        "Export a recorded review decision",
        "Draft and reviewed states stay distinct",
        "The workbook retains accepted findings, source evidence, corrections, page coverage and the run log. Numeric precision and identifiers are preserved. OCR retries archive the previous run before replacing it.",
    ),
    (
        "22-nested-header-groups.jpg",
        "Structure survives extraction.",
        "Header paths and merged-cell origins stay visible",
        "All 16 complex development cases match 962 cells. Three public digital fixtures match 261 cells under disclosed policies. These cases helped repair the engine; they are not a blind hidden-PDF evaluation. This nested example highlights the shared order ID origin.",
    ),
    (
        "29-workflow-guide.png",
        "A reproducible accuracy workflow",
        "Built for the INCUXAI challenge 2026",
        "Double-click START_DAMNLENS.cmd; Local AI runs without a key after setup. Optional Gemini uses your own key. Three live dummy first pages match 360 cells; two earlier provider failures are disclosed. These are development checks, not hidden accuracy or an official score.",
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
        canvas = Image.new("RGB", (1920, 1080), "#f5f7fb")
        d = ImageDraw.Draw(canvas)
        d.rectangle((0, 0, 1920, 87), fill="#111b31")
        d.text(
            (40, 23),
            "DamnLens AI Agent / Document AI",
            font=font(30, True),
            fill="#edf2ff",
        )
        d.text(
            (1275, 34),
            "INCUXAI 2026  /  APPLICATION WALKTHROUGH",
            font=font(15, True),
            fill="#a9bad5",
        )
        shot = Image.open(SHOTS / image).convert("RGB")
        shot.thumbnail((1330, 900), Image.Resampling.LANCZOS)
        x = 30 + (1330 - shot.width) // 2
        y = 112 + (900 - shot.height) // 2
        d.rounded_rectangle(
            (x - 1, y - 1, x + shot.width + 1, y + shot.height + 1),
            radius=8,
            fill="#dce5f3",
        )
        canvas.paste(shot, (x, y))
        d.text((1400, 150), f"{i + 1:02d} / 10", font=font(18, True), fill="#7895c7")
        yy = wrapped(d, title, (1400, 205), font(40, bold=True), "#263c5f", 470, 10)
        yy = wrapped(d, subtitle, (1400, yy + 26), font(20, True), "#5475ac", 465, 9)
        wrapped(d, body, (1400, yy + 30), font(24), "#657c9f", 465, 15)
        d.text(
            (40, 1039),
            "Captioned walkthrough of actual application screens. Editorial timing; not a real-time recording.",
            font=font(15),
            fill="#879bb9",
        )
        d.rectangle((1400, 930, 1870, 935), fill="#dfe7f4")
        d.rectangle((1400, 930, 1400 + int(470 * (i + 1) / 10), 935), fill="#678bd1")
        p = TMP / f"frame-{i:02d}.png"
        canvas.save(p)
        paths.append(p)
    sequence = TMP / "frames.txt"
    sequence.write_text(
        "".join(f"file '{p.as_posix()}'\nduration 15\n" for p in paths)
        + f"file '{paths[-1].as_posix()}'\n",
        encoding="utf-8",
    )
    out = ROOT / "docs" / "damnlens-demo.mp4"
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
