# DamnLens AI Agent application demonstration

**03:42. Live Chrome application recording, with no audio or captions.**

The video shows the working local application being used. Two original window recordings were made with Chrome's screen-sharing recorder. Navigation and idle pauses are cut, and related operations are grouped together. Retained extraction footage plays at recorded speed. The final MP4 is 1920 × 1080, H.264, encoded at 30 fps from variable-frame-rate recordings. There are no generated screenshots, scoring labels or presentation slides.

| Time | Functionality shown | Result to inspect |
|---|---|---|
| 00:00 | Digital PDF and source evidence | Three pages joined into 31 rows and 12 columns; row selection highlights the original source; page coverage is available. |
| 00:43 | Scanned PDF and local OCR | Actual OCR progress, followed by 20 rows and 12 columns from two image-only pages; reconstructed data beside the scan. |
| 01:31 | 50-page extraction and integrity | Actual processing of 50 pages into 500 rows and 12 columns. Repeated headers are removed; 490 duplicate business rows are retained and flagged. |
| 02:10 | Nested headers and merged cells | Parent/child headers and a shared order ID traced back to its merged source cell. |
| 02:26 | Validation and review | Missing fields, balance errors and a total mismatch; saved correction history; source-check confirmation, acknowledgement and a review note. |
| 03:27 | Reviewed Excel download | Export contents, review status and an actual workbook download. |

All demonstrated documents are fictional fixtures. The 50-page stress document repeats a ten-row page 50 times; it demonstrates capacity and duplicate preservation, rather than 50 different layouts. The bank statement deliberately contains source errors: its stated debit total of 2,600 differs from the contributing rows' sum of 2,500. Those values and their findings remain visible after review and in the downloaded workbook.

The blank currency was explicitly changed to USD between the two recording sessions. The video shows its actual saved correction history; it does not show typing that edit. Five remaining findings are acknowledged for export. Their presence is not presented as a clean validation result.

Processing in this recording uses Local AI. Gemini appears as an optional workflow on the opening screen; the recording makes no live Gemini request. This demonstration is not a measurement of accuracy on unseen documents.

## Rebuild and verification

Install `requirements-dev.txt`, then run `python scripts/build_demo.py`. Use `python scripts/build_demo.py --verify-only` to verify the existing movie without rendering it again.

- Original recordings: `recordings/damnlens-session-01.webm` and `recordings/damnlens-session-02.webm`.
- Exact cuts: `demo-timeline.json`; navigable MP4 chapters: `demo-chapters.txt`.
- Source hashes: `recordings/capture-manifest.json`.
- Media checks: `../reports/demo-verification.json`.
- Demonstrated result and downloaded-workbook checks: `../reports/demo-live-check.json`.

The builder requires the original recordings. It does not fall back to still images.
