# DamnLens AI Agent submission demo

**3 minutes 52 seconds. 1920 × 1080. Captions only; no audio.**

This edited walkthrough uses authentic browser captures, a read-only render of the actual exported XLSX, and the published CI run. Close-ups and display times are editorial; this is not an uncut speed recording. All application examples use fictional data. Gemini screens show the recorded live test; making the video sent no new cloud requests.

The five rubric labels show **available marks**, not marks awarded. The closing case for the project is traceability, explicit uncertainty, optional independent AI checking and reproducibility. No win or hidden-PDF accuracy is claimed.

| Time | Screen / requirement | Burned-in caption |
|---|---|---|
| 00:00–00:08 | DamnLens AI Agent | Turn PDFs and scans into structured Excel, with source evidence and a recorded review decision. |
| 00:08–00:18 | Two workflows. One accuracy process. | Local AI works without a key or per-page API charges. Optional Gemini independently checks difficult pages after explicit cloud authorization. |
| 00:18–00:29 | Automatic tables, headers and alignment | The native invoice PDF becomes one 12-column table across three pages. All 31 rows and the original total are retained. |
| 00:29–00:37 | Click a cell. Inspect the original. | Selecting invoice row 12 opens page two and highlights its original location. Every exported row retains its source reference. |
| 00:37–00:48 | Image-only PDF to structured rows | The inventory PDF has no embedded text. Local English OCR reconstructs 20 rows and 12 columns across both scanned pages. |
| 00:48–00:56 | Standalone images follow the same workflow | This PNG input yields 10 rows and 12 columns. Its 120 data cells and all 12 headers match the fictional source. |
| 00:56–01:07 | The full 50-page boundary, exercised | A fresh 50-page run preserves 500 rows and 12 columns. It removes 49 repeated headers and flags 490 duplicate rows without deleting them. |
| 01:07–01:14 | Coverage is visible page by page | All 500 rows retain source evidence. Page coverage exposes missing table pages. OCR confidence is shown separately. |
| 01:14–01:25 | Nested headers and merged-cell origins | Nested line items retain header paths and shared order IDs. Inherited values keep their source geometry and remain flagged for review. |
| 01:25–01:36 | One logical row. Two source fragments. | A description continues on page two. The joined table keeps six rows and 12 columns, with both source parts available for inspection. |
| 01:36–01:47 | Find errors before they enter Excel | The deliberately faulty bank statement triggers missing values, balance errors and a total mismatch: stated 2,600 versus a 2,500 row sum. |
| 01:47–01:56 | Corrections are traceable | An explicit correction preserves the previous value, records the change and reruns validation. Later edits invalidate any earlier review decision. |
| 01:56–02:05 | Review is a recorded decision | Extraction completes as a draft. Review records source checks and requires a note for acknowledged findings, tied to the current data snapshot. |
| 02:05–02:14 | Export with findings and provenance | The export clearly distinguishes draft and reviewed states. Accepted findings remain visible alongside data, evidence, corrections, coverage and the run log. |
| 02:14–02:24 | The actual exported workbook | This is a rendered range from the submitted invoice XLSX: twelve aligned columns, preserved identifiers, typed numbers, dates and percentages. |
| 02:24–02:35 | Recover without silently starting over | The recorded recovery run resumes a verified completed page, then extracts the next page. Checkpoints must match the source, configuration and engine. |
| 02:35–02:48 | Optional Gemini, with bounded requests | Recorded live test: local OCR retains all 20 rows. Gemini checks one scanned page; the one-request cap skips page two. Usage stays visible. |
| 02:48–02:57 | Independent candidates, explicit fallback | Cloud candidates remain separate for review. Three dummy first-page checks matched 360 cells; two earlier HTTP 503 failures retained the local results. |
| 02:57–03:09 | Measured results, with ground truth | The three submission samples match 864 of 864 data cells. Separate development cohorts cover 16 complex cases and 15 varied layouts. |
| 03:09–03:19 | Uncertainty becomes a review task | Expanded public and scan checks pass 10 of 11 strict cases. One Sl./SI. header ambiguity is flagged. Development results do not establish hidden-PDF accuracy. |
| 03:19–03:29 | Quality checks judges can inspect | The published CI run passed 158 tests on each of Windows, Ubuntu and macOS, plus static quality gates and a non-root Docker conversion check. |
| 03:29–03:38 | Easy to launch. Easy to reproduce. | Install Python 3.12, extract the full project and double-click START_DAMNLENS.cmd. Bundled models run locally after the first dependency installation. |
| 03:38–03:45 | A complete, inspectable submission | Source, launchers, three PDF–Excel pairs, accuracy reports and this demo are included in the repository and submission ZIP. |
| 03:45–03:52 | Why DamnLens stands out | Source-linked extraction, explicit validation, optional Gemini review and reproducible checks address all five judging categories. |

## Submission files

- `damnlens-demo.mp4`: ready-to-submit video with captions burned in.
- `damnlens-demo.srt`: matching optional subtitles; captions are already visible in the movie.
- `demo-chapters.txt`: chapter timestamps.
- `demo-storyboard.json`: edit specification with original capture crops.
- `../reports/demo-verification.json`: codec, duration, silent-stream check, full decode, hashes and source-capture manifest.
- `../reports/demo-extraction-check.json`: fresh 50-page and PNG checks.

## Rebuild

Install `requirements-dev.txt`, then run `python scripts/build_demo.py`. Use `--frames-only` to inspect before encoding, or `--verify-only` to verify an existing movie. The XLSX image is a read-only render of `samples/converted/01_invoice_register.xlsx`, `Table 1`, A1:L12, without changes to values or formatting.

## Evidence scope

The 50-page fixture repeats the first invoice page 50 times to test boundary handling and duplicate preservation; it is not a 50-layout diversity test. The PNG is inventory page one rasterized at 180 DPI. The 864-cell sample, 16-case complex and 15-case varied cohorts are separate development results. Expanded 10/11 checks include selected checkpoints rather than complete transcription of every public document; one ambiguous header remains flagged. The small live Gemini cohort covers three dummy first pages (360 cells, 36 headers), with two earlier provider failures disclosed. See the accuracy, expanded evaluation and Gemini reports for comparison policies. The CI screen shows source commit `c8d8b2b`, [run 38715554376](https://github.com/rayanakarthikeyan/damnlens-ai-agent/actions/runs/38715554376).
