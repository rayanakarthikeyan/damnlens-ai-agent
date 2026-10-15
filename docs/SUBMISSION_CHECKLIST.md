# INCUXAI 2026 submission checklist

| Requirement | Implementation | Evidence |
|---|---|---|
| Up to 50 PDF pages | Hard input guard at 50, page-by-page extraction | 50-page/501-row test; 51-page rejection test |
| Tables with 10+ columns | Dynamic-width table data model | All three fixtures have 12 columns |
| Scans and images | RapidOCR + bundled English PP-OCRv3 recognition + OpenCV layout | Two-page image-only scan, 240 matching cells |
| Automatic table/header detection | Native ruled tables, aligned text headers, OCR grid and borderless fallback | Native, borderless and scanned regression tests |
| Multi-page joining | Adjacent schema matching, repeated header removal, conservative headerless span matching | 3-page invoice; 50-page stress; headerless and duplicate tests |
| Errors and validation | Totals, arithmetic, balance transitions, empty/missing/type/sparse/duplicate/low-score/page checks | Deliberately faulty bank statement; raw JSON findings |
| Working application | Local FastAPI + offline browser workspace | `python run.py`; screenshots and demo |
| Complete source | Public GitHub repository + downloadable archive | https://github.com/rayanakarthikeyan/ledgerlens |
| Setup and execution | Python launchers, manual setup, CLI, Dockerfile | README |
| 3 sample PDFs and Excel | Original fictional invoices, scan and bank statement | `samples/` and `samples/converted/` |
| Accuracy and validation report | Reproducible cell and row comparison | `reports/ACCURACY_REPORT.md`, raw JSON and ground truth |
| 2–5 minute demo | Captioned walkthrough of real application screens | `docs/ledgerlens-demo.mp4` |
| Library/API credits | Library licenses, OCR model source and hash, AI-assistance disclosure | THIRD_PARTY_NOTICES.md and models/README.md |
| Public/dummy documents only | All fixtures generated for this project | Fixture generator; no private data in repository |
| Solo / team up to 3 | User participation is not registered by this app | Confirm entrant/team details during submission |
| Original core logic | Project-specific layout, stitching, validation, provenance, review and export logic; AI-assisted creation credited | Source history and architecture explanation |
| Submit by deadline | Brief says 16 October 2026, 7 PM, without timezone | User must confirm timezone and actual form URL; provided `[ADD LINK]` is not usable |

No claim is made about winning, hidden-test accuracy, eligibility beyond the supplied brief, or actual submission. The original-work rule requires honest disclosure of AI assistance; only the organizer can resolve its interpretation.

## Suggested 3-minute judging path

1. Launch the app and choose **The invoice register**. Check 3 pages → 1 table, 31 rows, 2 repeated headers removed.
2. Click a row from page 2 and inspect the original highlight. Toggle the source panel off to inspect all columns.
3. Choose **The scanned inventory**. Note that the PDF has no embedded text. Watch OCR progress and review the 20 rows.
4. Choose **The bank statement**, open Validation and locate a finding. Correct a source value deliberately and show recorded corrections/revalidation.
5. Export Excel. Open Overview, Table 1, Validation, Evidence and Corrections.
6. Open Accuracy report and show the ground-truth methodology. Run the automated suite for 50-page and integrity evidence if time permits.
