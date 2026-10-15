# INCUXAI 2026 submission checklist

| Requirement | Implementation | Evidence |
|---|---|---|
| Up to 50 PDF pages | Hard input guard at 50, page-by-page extraction | 50-page/501-row test; 51-page rejection test |
| Tables with 10+ columns | Dynamic-width table data model | All three fixtures have 12 columns |
| Scans and images | RapidOCR + bundled English PP-OCRv3 recognition + OpenCV layout | Two-page image-only scan, 240 matching cells |
| Automatic table/header detection | Native ruled tables, aligned text headers, OCR grid and borderless fallback | Native, borderless and scanned regression tests |
| Multi-page joining | Independent streams, context/schema/span matching, repeated header removal, conservative description continuation with both source parts | 3-page invoice; 50-page stress; split-row and distinct-account cases |
| Errors and validation | Totals, arithmetic, balance transitions, empty/missing/type/sparse/duplicate/low-score/page checks | Deliberately faulty bank statement; raw JSON findings |
| Working application | Local FastAPI/browser workspace; default keyless local AI plus optional Gemini assistance | `python run.py`; `docs/WORKFLOWS.md`; screenshots and demo |
| Complete source | Public GitHub repository + downloadable archive | https://github.com/rayanakarthikeyan/damnlens-ai-agent |
| Setup and execution | Double-click Windows launcher, verified bootstrap, offline judge checks, manual setup, CLI, Dockerfile | README; START_DAMNLENS.cmd; setup_judges.py |
| 3 sample PDFs and Excel | Original fictional invoices, scan and bank statement | `samples/` and `samples/converted/` |
| Accuracy and validation report | Separate sample, varied, complex and public-reference cohorts; explicit methodology | `reports/JUDGE_EVALUATION.md`, `ACCURACY_REPORT.md`, raw JSON and ground truth |
| 2–5 minute demo | Captioned walkthrough of real application screens | `docs/damnlens-demo.mp4` (150 seconds; includes two-workflow setup and complex structure/recovery) |
| Library/API credits | Library licenses, OCR model source and hash, AI-assistance disclosure | THIRD_PARTY_NOTICES.md and models/README.md |
| Public/dummy documents only | Original dummy fixtures plus explicitly downloaded, pinned public reference PDFs | Generators; public URLs/checksums/annotation license; no private data |
| Solo / team up to 3 | User participation is not registered by this app | Confirm entrant/team details during submission |
| Original core logic | Project-specific layout, stitching, validation, provenance, review and export logic; AI-assisted creation credited | Source history and architecture explanation |
| Submit by deadline | Brief says 16 October 2026, 7 PM, without timezone | User must confirm timezone and actual form URL; provided `[ADD LINK]` is not usable |

No claim is made about winning, hidden-test accuracy, eligibility beyond the supplied brief, or actual submission. The original-work rule requires honest disclosure of AI assistance; only the organizer can resolve its interpretation.

## Suggested 3-minute judging path

1. Launch the app and choose **The invoice register**. Check 3 pages → 1 table, 31 rows, 2 repeated headers removed.
2. Click a row from page 2 and inspect the original highlight. Toggle the source panel off to inspect all columns.
3. Choose **The scanned inventory**. Note that the PDF has no embedded text. Watch OCR progress and review the 20 rows.
4. Choose **The bank statement**, open Validation and locate a finding. Correct a value deliberately, show corrections/revalidation, complete review with a note, and inspect the reviewed export.
5. Export Excel. Open Overview, Table 1, Validation, Evidence, Corrections, Page coverage and Run log.
6. Open Accuracy report and show the ground-truth methodology. Run the automated suite for 50-page and integrity evidence if time permits.
7. In Accuracy & coverage, run a complex example: nested line items or a split row. Inspect Header groups, shared-cell source geometry or Part 2. The optional Excel Structure sheet preserves the reconstruction. An interrupted run exposes Resume extraction; the offline judge command demonstrates verified-page recovery.
8. Open Workflow guide to compare Local AI with Gemini-assisted AI. Optional cloud testing needs the judge's own key, explicit authorization and request limit. Inspect AI workflow for independent candidates, usage, discrepancies and skipped pages; the main data is never silently overwritten.

## v1.3 additional evidence

- 100 passing tests, 16/16 complex development cases (962/962 cells), and 3/3 public digital reference cases (261/261 cells under disclosed comparison policies).
- Eight offline runtime checks need no development dependencies, including nested structure, split-row evidence and checkpoint recovery.
- Full expected arrays, source geometry, baselines, annotation credits and remaining risks are published. These cases were used for development; no hidden accuracy or organizer score is claimed.

## v1.1 accuracy-workflow improvements

- An operational UI replaces promotional copy and illustrative spreadsheet content.
- Page coverage, source evidence, automated findings and human review are separate facts.
- Review requires source-check confirmation and explicit acknowledgement/note for outstanding findings. Subsequent corrections invalidate review.
- OCR retries preserve downloadable prior runs and cannot serve stale result exports while processing.
- Continuing table streams are matched independently, with stricter checks against joining similar but unrelated schemas.
- Zero values, Indian grouping without decimal points, long numeric identifiers and source decimal precision have regression coverage.
