# Verification record

Verified locally on Windows with Python 3.12.14.

- **74 automated tests passed**. The raw JUnit record is `reports/tests.xml`. One upstream Starlette warning advises moving its test transport to HTTPX2; it does not affect extraction or the running application.
- **864/864 synthetic fixture data cells match ground truth**, with exact headers and exact-row recall. See `reports/benchmark.json` and `reports/ACCURACY_REPORT.md` for methodology and limitations.
- **50-page stress test:** one joined table, 501 rows, 12 columns, all source cells preserved, 49 repeated headers removed.
- **Borderless regression:** two-page digital fixture preserves multiword headers and all data cells, with alignment marked for review.
- **Browser flow:** real invoice, scan and bank fixture extraction; row-to-source highlight on page 2; validation-to-row navigation; missing-currency correction; finding count changes from 6 to 5; one correction remains in history; Excel downloaded successfully.
- **Export inspection:** seven sheet types, draft/reviewed metadata, typed numbers/dates/percentages, source decimal precision, preserved identifiers/long values, filtered/frozen table data, matching evidence rows and text-only untrusted formula-like content.
- **CLI:** bank statement exported to Excel and JSON, with 21 rows and six source findings.
- **Visual inspection:** rendered sample PDFs inspected for legibility and table alignment. Desktop and mobile browser screenshots are in `docs/screenshots/`.
- **Video:** H.264 MP4, 1920 × 1080, 12 frames/second, exactly 150 seconds. Captioned walkthrough using real UI captures, not an uncut performance recording.
- **Static checks:** Python compilation and JavaScript syntax checks pass. Python and frontend sources are formatted for readability.

Windows and Linux CI results are visible under the repository's Actions tab. The previous release passed on both operating systems. Docker configuration is supplied but was not manually verified locally.

## Accuracy workflow audit (v1.1)

- The UI now presents a document queue, observed quality facts, an agent pipeline, exception inbox, source comparison, severity/flagged-row filters, page coverage and timestamped execution events.
- Review is explicitly separate from extraction completion and from OCR confidence. Completing review binds a decision to the data fingerprint. Outstanding findings require acknowledgement and a note; subsequent changes invalidate review and retain its prior decision. Saving an unchanged cell does not invalidate review.
- Browser verification: a bank fixture finding locates page 2 and the correct row; correcting missing currency reduces six findings to five; completing review retains those five accepted findings; the export modal clearly shows a reviewed decision with three errors and two warnings.
- Safe retry verification: the current corrected/reviewed run is archived before OCR retry. Tests verify prior-run Excel/JSON downloads and that a pending replacement run cannot export a stale result.
- Multi-table accuracy: a real two-page PDF with two separate continuing table streams produces two joined tables with both rows preserved in each. Similar wide schemas with different identity headers are kept separate.
- Numeric integrity: zero values, Indian grouping without decimals, source decimal precision and values beyond Excel's 15-digit numeric precision have dedicated regression coverage.
- Source documents and extracted content remain data, never executable agent instructions. Benchmark accuracy remains measured against explicit ground truth, not inferred from OCR scores.

- Live Windows stress verification exposed a temporary file-sharing lock on progress persistence. Atomic writes now use unique temporary files and bounded exponential retries on PermissionError; a regression simulates two locked replacements and verifies successful persistence with no leftover temporary file.

## DamnLens judge audit (v1.2)

- Renamed UI, API metadata, workbook titles, sample documents, demo, README and GitHub repository to DamnLens AI Agent. Existing local data and the legacy data-directory environment variable remain compatible.
- All 15 varied development cases now match their intended headers and ordered cells, compared with 5 before the fixes. The 14 table cases contain 1,440 data cells. Source PDFs, explicit truth and raw measurements are included. This is a development regression set, not an independent hidden evaluation.
- Added native PDF rotation normalization with viewer-coordinate evidence, right-angle OCR orientation recovery, header-boundary assignment for right-aligned borderless values, selective inked-empty-cell OCR retry and sparse group-heading handling.
- Financial checks now use decimal arithmetic and a fixed half-cent rounding tolerance. Regressions include a one-cent error on a large total and an amount beyond binary floating-point precision.
- The Windows `START_DAMNLENS.cmd --judge-test --offline` path passes all five runtime-only smoke checks: exact cells/headers and workbook inspection for the three fixtures, 50-page duplicate preservation and 51-page rejection.
- Typography: relative font units, 13px minimum secondary labels, 14px data cells, 15px explanations, darker foregrounds and a persisted Large mode at 112.5%. Desktop 1440px and mobile 390px layouts were inspected without horizontal page overflow; source tables retain their own horizontal scrolling.
- Browser verification reran invoice, scan and bank samples, checked page-two row highlighting, coverage/log tabs, explicit review acknowledgement, export summary and the visible 15-case audit. The dummy review note identifies the operation as an automated UI demonstration rather than an entrant or judge decision.
- Setup diagnostics verify pinned package versions, native imports, model/dictionary hashes and writable files. Healthy launches skip pip. Server launch reserves an available loopback port and opens the browser after readiness.
- Updated 150-second demo uses the renamed, larger-text UI. It remains a captioned walkthrough, not an uncut performance recording.
