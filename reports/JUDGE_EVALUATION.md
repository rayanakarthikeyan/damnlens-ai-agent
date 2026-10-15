# Judge evaluation — DamnLens AI Agent

This is a development self-assessment against the supplied rubric, not an official judging result or a prediction of hidden-PDF performance. All documents used here are fictional and were generated for this project. The same developer used the audit failures to improve the implementation; the final audit is a regression set, not a held-out test.

## Provisional rubric assessment

| Area | Weight | Provisional mark | Evidence and remaining risk |
|---|---:|---:|---|
| OCR and extraction | 30 | 26 | 864/864 cells on the three submission samples; broader checks include rotated, lower-contrast and borderless printed scans. English only; no independent real-world corpus, handwriting or severe damage evaluation. |
| Multi-page and complex tables | 25 | 21 | 50 pages / 501 rows / 12 columns; two independently continuing streams; headerless continuation; repeated-header removal; sparse group headers and mixed native/scan pages. Arbitrary nested cells, multi-line headers and rows split across page boundaries remain risks. |
| Alignment and integrity | 20 | 19 | Exact cell order and headers, duplicate multiplicity, evidence transforms, precision-safe identifiers, decimal financial checks, source errors preserved, corrections and review fingerprint. Borderless inference remains heuristic. |
| Automation and recovery | 15 | 14 | Native/OCR routing, orientation recovery, selective empty-cell OCR, page findings, persistent queue, bounded Windows file-write retries, archived prior runs and blocked stale exports. No mid-page checkpoint or cancellation. |
| Code quality and usability | 10 | 9 | Pinned dependencies, offline model assets and checksums, double-click bootstrap, CLI, readable UI, persisted Large text mode, automated tests and cross-platform CI. Docker/macOS execution is not locally verified. |
| **Total** | **100** | **89** | **Conservative reviewer estimate. Actual judges can assign a different score.** |

## Measured before-and-after development audit

Exact cases: **5/15 before → 15/15 after**. The 14 table-bearing cases contain 1,440 expected data cells; the fifteenth is prose with no table. All output cells and headers match in the final run, and the narrative case produces no invented table. Borderless alignment still receives a review finding; repeated legitimate rows in the mixed case are retained and flagged.

| Variation | Before cell match | After cell match | Exact headers after | Final status |
|---|---:|---:|---|---|
| right_aligned_native | 96/96 | 96/96 | True | Pass |
| borderless_native | 96/96 | 96/96 | True | Pass |
| merged_group_header | 30/120 | 96/96 | True | Pass |
| pdf_rotation_90 | 3/99 | 96/96 | True | Pass |
| pdf_rotation_180 | 0/108 | 96/96 | True | Pass |
| pdf_rotation_270 | 3/108 | 96/96 | True | Pass |
| scan_clean | 95/96 | 96/96 | True | Pass |
| scan_borderless | 61/96 | 96/96 | True | Pass |
| scan_skew_2deg | 96/96 | 96/96 | True | Pass |
| scan_degraded | 96/96 | 96/96 | True | Pass |
| scan_sideways_90 | 0/108 | 96/96 | True | Pass |
| scan_sideways_180 | 0/108 | 96/96 | True | Pass |
| scan_sideways_270 | 3/99 | 96/96 | True | Pass |
| mixed_native_scan | 191/192 | 192/192 | True | Pass |
| narrative_no_table | No table | No table | True | Pass |

## Gaps fixed during review

1. PDF rotation previously scrambled headers and columns. Extraction now runs in native text coordinates and maps row evidence back into the original viewer orientation.
2. Physically rotated scans previously produced misaligned output. Weak orientation evidence triggers bounded right-angle OCR attempts with inverse coordinate mapping.
3. Borderless scans assigned right-aligned values to the nearest next header. Header boundaries now determine assignment; a table header is required to avoid interpreting prose as a table.
4. An isolated digit missed by page OCR left a populated grid cell blank. Visibly inked empty cells receive a local crop OCR retry, with no value inferred from arithmetic.
5. Sparse spanning group labels above column names became data. A real header within the first three rows can supersede preceding sparse group rows.
6. Floating-point checks and a relative tolerance could miss a one-cent error on large totals. Validation now uses Decimal and a fixed half-cent rounding tolerance.
7. Several UI labels shrank to 6–11px. Relative font units now enforce a 13px secondary minimum at standard size, with 14px table cells, 15px explanations, darker text and a persisted 12.5% Large mode.
8. Launch scripts reinstalled on every run. The standard-library bootstrap verifies versions, native-library imports and bundled asset hashes, installs only when needed, reports actionable failures and supports offline diagnosis/judge checks.

## Evidence and reproduction

- `reports/judge-audit-before.json` and `reports/judge-audit-after.json`: raw per-case measurements, row counts, exact headers, findings and timings.
- `evaluation/pdfs/`: 15 original audit PDFs; `scripts/judge_audit.py` defines independent source values and rendering.
- `evaluation/ground_truth.json`: expected headers and ordered rows, including duplicate multiplicity.
- `tests/test_judge_audit.py`: all audit cases plus coordinate provenance, offline bootstrap behavior and cent-level financial regressions.
- `START_DAMNLENS.cmd --judge-test --offline`: runtime-only checks after first setup; no pytest/ReportLab installation required.
- `python scripts/judge_audit.py`: regenerate and measure all varied cases with development dependencies installed.
- `python -m pytest -q`: full extraction, API, review, export, recovery and audit suite.

Cell accuracy compares normalized whitespace at the same row and column and divides by the larger actual/expected cell count. Wrong row order, missing cells and extra cells are penalized. Exact case pass also requires the intended table count, all headers and all ordered rows. The no-table case passes only when no table is fabricated. OCR recognition confidence is never used as measured accuracy.

## Remaining competition risks

A clean synthetic pass does not establish performance on hidden PDFs. The largest remaining technical risk is complex merged/nested layouts and changing or multi-line schemas. The workflow surfaces uncertain alignment and uncovered pages, but an unrecognized secondary table on an otherwise extracted page can still require visual inspection. Only printed English OCR is evaluated. The 150-second demo is a captioned walkthrough of actual screens, not an uncut performance recording. AI coding assistance is disclosed in the repository; entrant eligibility and the final submission link must be confirmed with the organizer.
