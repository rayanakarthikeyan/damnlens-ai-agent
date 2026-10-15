# Verification record

## Submission recording — 15 October 2026

The final video is **3:49**, full-HD H.264 at 24 fps, with captions below the application and no audio. It uses **1,396 timestamped browser captures** collected while operating the working app, across 27 recorded operations. It replaces the earlier screenshot presentation. Idle gaps between steps and one static download pause are removed; captured extraction footage is not accelerated. No scoring sidebars, production banners, counters or timers are added. The original browser viewport is 1265 × 712 with a variable sampling rate; the output is encoded at 24 fps.

[The demonstrated-job checks](../reports/demo-live-check.json) verify the actual invoice, scan, image, 50-page, nested and split-row results. The downloaded workbook has all seven expected sheets, the explicit currency correction and five retained findings. Gemini configuration is shown without making a cloud request. [The media report](../reports/demo-verification.json) records full decoding, duration, source and output hashes. The raw recording, timeline and optional subtitles are included for rebuilding the final movie.

Application runtime source is unchanged by this media revision. Python and frontend quality checks pass.

## Earlier application verification

Verified locally on Windows with Python 3.12.14.

- **115 automated tests passed**. The raw JUnit record is `reports/tests.xml`. One upstream Starlette warning advises moving its test transport to HTTPX2; it does not affect extraction or the running application.
- **864/864 synthetic fixture data cells match ground truth**, with exact headers and exact-row recall. See `reports/benchmark.json` and `reports/ACCURACY_REPORT.md` for methodology and limitations.
- **50-page stress test:** one joined table, 501 rows, 12 columns, all source cells preserved, 49 repeated headers removed.
- **Borderless regression:** two-page digital fixture preserves multiword headers and all data cells, with alignment marked for review.
- **Browser flow:** real invoice, scan and bank fixture extraction; row-to-source highlight on page 2; validation-to-row navigation; missing-currency correction; finding count changes from 6 to 5; one correction remains in history; Excel downloaded successfully.
- **Export inspection:** seven sheet types, draft/reviewed metadata, typed numbers/dates/percentages, source decimal precision, preserved identifiers/long values, filtered/frozen table data, matching evidence rows and text-only untrusted formula-like content.
- **CLI:** bank statement exported to Excel and JSON, with 21 rows and six source findings.
- **Visual inspection:** rendered sample PDFs inspected for legibility and table alignment. Desktop and mobile browser screenshots are in `docs/screenshots/`.
- **Video:** H.264 MP4, 1920 × 1080, 24 frames/second, exactly 229 seconds. Captioned walkthrough using real UI captures, not an uncut performance recording.
- **Static checks:** Python compilation and JavaScript syntax checks pass. Python and frontend sources are formatted for readability.

Windows and Linux CI results are visible under the repository's Actions tab. The workflow runs the full suite, fresh bootstrap, offline judge checks and pinned public PDF comparisons on both systems. Docker configuration is supplied but was not manually verified locally.

## Expanded source checkpoints (v1.4)

The new source-reviewed public cohort improved from 3/11 to 10/11 strict checkpoint cases. One header-only ambiguity is retained and flagged, with all 376 checked data cells and dimensions correct. Full scope, reference errata, first-pass provenance, partial-audit limits and reproduction are in `reports/EXPANDED_EVALUATION.md`. Fifteen new regression tests cover the repaired behavior. Both OCR models ship offline with bootstrap and checkpoint signatures. The real UI run shows the header warning despite a high mean recognition score; screenshot `24-ocr-disagreement-review.jpg` records it.

## Complex structure and recovery (v1.3)

- Full Windows regression: **100 passed**, including all existing varied audit cases and new complex/checkpoint/API regressions. Tests include native body rows containing header words, a single low-confidence OCR cell and geometric punctuation order.
- Complex development cohort: **16/16 exact cases, 962/962 data cells**, with exact headers/table counts. The original twelve cases improved from 2/12 to 12/12; four additional blank/nested cases have no baseline. PDFs, truth, JSON and converted Excel are in `evaluation/complex/`.
- Public reference cohort: **3/3, 261/261 cells**, using independent pinned Camelot annotations. `foo.pdf` first passed 30/35, prompting a geometric character fix. The final result is development evidence, not held out. `column_span_2.pdf` uses an explicitly disclosed anchor-cell comparison rather than raw shared-value output.
- All original submission workbooks were regenerated: **864/864** sample cells, including 240/240 scanned cells; the faulty bank fixture retains all six intended findings.
- Windows launcher: **8/8** runtime-only offline checks, now including nested structure, two source parts for a continued row and recovery after a deliberate interruption.
- Checkpoints: resuming a three-page invoice reuses exactly the first two completed pages and extracts only page three. Source/mode changes, malformed JSON and checksum tampering invalidate caches. Interrupted current-page work restarts.
- Browser: a real interrupted split-row job resumed page one from cache, extracted page two and kept six logical rows with twelve columns. Selecting Part 2 highlighted the continued description on page two. Selecting an inherited order ID in the nested example highlighted the original merged source rectangle. Header paths and shared-value warnings were visible; console had no errors.
- Excel: complex cases add Structure only when relevant; ordinary samples retain seven sheets. Evidence includes both source fragments for continued rows, and shared values retain origin geometry.
- Screenshots 18–22 and the updated 229-second captioned demo show the real application. Scores in `JUDGE_EVALUATION.md` are subjective rubric estimates, not organizer results or hidden-PDF accuracy measurements.

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
- Updated 229-second demo uses the renamed, larger-text UI. It remains a captioned walkthrough, not an uncut performance recording.
