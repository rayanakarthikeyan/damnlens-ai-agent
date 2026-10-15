# DamnLens AI Agent application demonstration

**03:49. Application screen recording with captions and no audio.**

The video records operating the working browser application: PDF selection and extraction, source inspection, local scanned OCR, an image result, 50-page processing, complex headers and source parts, validation, an explicit correction, review and an actual Excel download. It uses timestamped browser frames captured during those operations, rather than the earlier screenshot presentation. Idle gaps between steps and one static download pause are removed. Extraction footage is not accelerated. The original browser capture is 1265 × 712 with a variable sampling rate; the final 1920 × 1080 movie encodes at 24 fps. Captions sit below the app. No scoring, production banners, sidebars, counters or timers are added.

All documents are fictional fixtures. The currency correction is an explicit demonstration edit, preserved in the history; source total and balance errors remain acknowledged findings. The Gemini section demonstrates configuration and request limits only. No new cloud request is made or represented as completed. The final accuracy screen is the saved development-sample benchmark, not a new hidden-document evaluation.

| Time | Operation | Caption |
|---|---|---|
| 00:00–00:08 | Local workflow | DamnLens AI Agent converts PDFs and scans into structured Excel. Start with the keyless Local AI workflow. |
| 00:08–00:20 | Invoice extraction | Upload a digital PDF. The agent detects tables and headers, joins three pages and preserves all 31 rows across 12 columns. |
| 00:20–00:28 | Invoice source | Click an extracted row to open its original source page and highlight the matching location. |
| 00:28–00:35 | Invoice coverage | Inspect page-by-page coverage and extraction routes. Every invoice row retains source evidence. |
| 00:35–00:57 | Scanned pdf | The image-only inventory PDF is read with local English OCR. Watch page progress, table reconstruction and validation complete. |
| 00:57–01:05 | Scan source | Inspect an OCR row against the scanned source. The two pages produce 20 rows and 12 columns. |
| 01:05–01:13 | Image result | Open the standalone PNG result: 10 rows and 12 reconstructed columns, with the original image available beside the data. |
| 01:13–01:25 | Fifty pages | The 50-page document produces 500 rows and 12 columns. Repeated headers are removed; duplicate business rows are preserved and flagged. |
| 01:25–01:32 | Fifty coverage | All 50 pages remain individually accessible, with source evidence retained for all 500 rows. |
| 01:32–01:39 | Nested headers | Expand the detected header structure to inspect parent and child labels in a nested line-item table. |
| 01:39–01:47 | Merged origin | Select a shared order ID to inspect the original merged cell. Inherited values retain their source geometry. |
| 01:47–01:53 | Split row first | A description continues across pages. The reconstructed row keeps links to both original source fragments. |
| 01:53–02:04 | Split row second | Switch to the second source part to inspect the continued description on page two. |
| 02:04–02:13 | Bank extraction | The bank statement includes intentional source errors. The agent preserves the values and flags them for review. |
| 02:13–02:21 | Bank validation | Validation identifies missing fields, running-balance errors and a total that does not reconcile. |
| 02:21–02:29 | Inspect total | Open the total finding to inspect its original row. The stated debit total is 2,600; contributing rows sum to 2,500. |
| 02:29–02:36 | Inspect missing cell | Locate the missing currency field in its source page before making an explicit correction. |
| 02:36–02:42 | Open correction | Open the cell editor. The original extracted value will remain in the correction history. |
| 02:42–02:50 | Save correction | For this demonstration, enter USD from the statement context. Validation reruns and the finding count updates from six to five. |
| 02:50–02:57 | Correction history | The correction history retains the original blank, the entered value, its location and the time of the edit. |
| 02:57–03:03 | Review dialog | Review confirms source checks and requires acknowledgement of outstanding findings. |
| 03:03–03:11 | Complete review | Record a review note. The remaining source errors stay visible and are acknowledged for this export. |
| 03:11–03:18 | Excel export | The Excel export includes structured data, review status, findings, source evidence, corrections, page coverage and the run log. |
| 03:18–03:23 | Download excel | Download the reviewed Excel workbook. Outstanding findings remain included in the file. |
| 03:23–03:33 | Gemini workflow | Optional Gemini assistance adds an independent reading of difficult pages. It requires a configured API key and explicit authorization. |
| 03:33–03:39 | Gemini request limit | Set a request limit and page scope. Google API plan and quotas apply; Local AI remains available without a key. |
| 03:39–03:49 | Accuracy report | The three bundled sample PDFs have matching Excel outputs and ground truth: 864 matching data cells, with headers checked separately. |

## Rebuild and evidence

Run `python scripts/build_demo.py` after installing `requirements-dev.txt`. The builder captions `recordings/damnlens-app-session.mp4` using `demo-timeline.json`; it never falls back to still screenshots. Use `--verify-only` to check an existing movie. Optional subtitles are in `recordings/damnlens-demo.srt`, separate from the final movie to prevent duplicate automatic subtitles. `recordings/capture-manifest.json` retains source-frame hashes and timestamps. `../reports/demo-verification.json` records media checks; `../reports/demo-live-check.json` verifies the actual demonstrated results and downloaded workbook.
