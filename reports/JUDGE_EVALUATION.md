# Judge evaluation — DamnLens AI Agent

## v1.5 optional Gemini workflow

Local AI remains the keyless default. Optional Gemini independently reads selected pages, retains candidates separately and routes discrepancies to source review; no automatic overwrites. Live checks matched 360/360 cells and 36 headers on three original dummy first pages. Two scan-PDF calls returned HTTP 503; a direct PNG route succeeded and both failures remain published. See [GEMINI_EVALUATION.md](GEMINI_EVALUATION.md) and [workflow mapping](../docs/WORKFLOWS.md). This establishes compatibility/recovery on a small development set, with no score increase or measured hidden-accuracy uplift.

## v1.4 expanded testing

The [expanded evaluation](EXPANDED_EVALUATION.md) covers seven previously unevaluated public PDFs and four rasterized scan derivatives. Source-frozen checkpoint results improved from 3/11 to **10/11 strict cases**. One scanned header retains an `Sl.`/`SI.` ambiguity with an explicit review finding; its checked data cells and dimensions match. Some checks cover selected columns/rows, not complete transcription. The original first pass, two disclosed annotation corrections and corrected baseline are preserved. These files became development cases after repairs. **This evidence does not justify a 100/100 or hidden-accuracy guarantee.**

The rubric estimate below remains a subjective readiness assessment. New fixes include reference-number header rows, unknown-vocabulary borderless schemas, nested table boundaries, partial/white rulings, numeric merged-cell geometry, merged-value-aware totals and a bundled secondary recognizer that records disagreements rather than hiding them.

**Provisional self-assessment: 95/100.** This is a subjective review against the supplied rubric, not an official score or a prediction of hidden-PDF performance. No organizer's hidden PDFs have been tested. The developer used these failures to repair the engine: final results are regression evidence, not a blind evaluation.

| Area | Weight | Estimate | Evidence and remaining risk |
|---|---:|---:|---|
| OCR and extraction | 30 | 28 | 864/864 submission cells; varied and complex printed-scan cases pass; 261/261 public reference cells. English only, small public digital corpus, no handwriting/severe damage evaluation. |
| Multi-page and complex tables | 25 | 24 | 50 pages / 501 rows / 12 columns; independent table streams; multi-line/grouped headers, vertical merges, nested line items and cross-page row parts. Arbitrary layouts and changing schemas remain uncertain. |
| Alignment and integrity | 20 | 19 | Exact ordered cells/headers, intentional blanks, ragged-value preservation, duplicate multiplicity, distinct account contexts, source geometry, decimal checks and precision-safe Excel. Borderless inference needs review. |
| Automation and recovery | 15 | 15 | Routing, bounded OCR recovery, persistent queue, Windows lock retries, verified page checkpoints, archived runs and stale-export protection. Interrupted current pages restart; no mid-page cancellation. |
| Code quality and usability | 10 | 9 | 150 tests, Windows/Ubuntu CI, pinned packages/model hashes, offline bootstrap, eight judge checks, readable UI and source inspection. Docker/macOS not manually verified locally. |
| **Total** | **100** | **95** | **Subjective readiness estimate; actual judges may score differently.** |

## Separate measured cohorts

| Cohort | Exact cases | Ordered matching data cells | Scope |
|---|---:|---:|---|
| Submission samples | 3/3 | 864/864 | Original dummy invoice, image-only inventory and deliberately faulty bank statement. Source errors must remain and be flagged. |
| Varied development audit | 15/15 | 1,440/1,440 | Fourteen table cases plus prose: rotations, skew, low contrast, borderless, grouped headers and mixed pages. |
| Complex development audit | 16/16 | 962/962 | Multi-line/hierarchical headers, vertical merges, nested line items, wrapped descriptions, cross-page parts, account boundaries and intentional blanks. |
| Public reference fixtures | 3/3 | 261/261 | Camelot public PDFs with independent upstream annotations; comparison policy below. All three are digital. |

Do not pool these into an independent-corpus accuracy claim. Synthetic fixtures were authored for this project. Public annotations are independent but their first-pass failures were used for development. OCR confidence is not measured accuracy.

The first twelve complex cases improved from **2/12 exact to 12/12**; four additional negative/nested cases bring the final result to 16/16. Those four have no baseline. The earlier varied audit improved from 5/15 to 15/15. Raw baselines are preserved.

## Gaps fixed

1. **Multi-line and hierarchical headers:** combine bounded physical header rows, retain full paths and qualify duplicate leaves (`2025 Sales`, `2026 Sales`). Native bold evidence helps separate headers from ordinary rows containing header words. JSON and the optional Excel **Structure** sheet retain hierarchy.
2. **Merged cells and nested line items:** share values only where explicit source geometry supports a span. Keep origin metadata, highlight the actual source cell when clicked and flag reconstruction for review. True empty source cells stay empty.
3. **Cross-page rows:** conservatively append an initial description-only fragment to a previously identified row. Preserve both raw cell arrays/pages/boxes, export both Evidence records and offer source-part buttons. Accepted joins remain review findings; numeric/identity gaps are never filled by arithmetic.
4. **Unrelated tables:** explicit account/invoice context prevents joining adjacent same-schema sections. Multiple compatible table streams can continue independently.
5. **Borderless alignment:** native words and OCR share column-boundary logic for right-aligned values and short wrapped headers. Inferred alignment remains flagged.
6. **OCR recovery:** visibly inked empty regions get recognition-only crops at two scales. Accept only agreeing text above the score threshold, record retries and flag review. One low-confidence cell triggers a finding even with a high row mean.
7. **Native glyph order:** reconstruct cell text geometrically; remove inferred whitespace only when it overlaps a separately drawn glyph. Preserve meaningful spaces and underscores. The public `foo.pdf` exposed this issue.
8. **Ragged rows:** pad to the widest observed row, preserving extra values rather than truncating them; flag uncertain alignment.
9. **Restart recovery:** save completed pages atomically. Reuse only verified checkpoints matching source bytes, engine/layout code, OCR mode/assets and relevant library versions. Corrupt, truncated or mismatched caches are recomputed. Retry OCR remains a fresh run and archives existing results.

## Public fixture policy and license

The manifest was pinned before the first comparison. It contains URLs, SHA-256 hashes and expected arrays from Camelot commit `92777b852e00933a5c4b9ba642601784604356cd` ([annotations](https://github.com/camelot-dev/camelot/blob/92777b852e00933a5c4b9ba642601784604356cd/tests/data.py)). Only annotations and the MIT license are included; no upstream extraction code is incorporated or executed. PDFs download explicitly on request rather than being redistributed.

- `foo.pdf`: 35 data cells and two header rows; first pass 30/35, final 35/35 after the glyph fix.
- `row_span_1.pdf`: 156 cells using upstream shared-value expectations; first and final passes exact.
- `column_span_2.pdf`: 70 cells using upstream **anchor-cell** expectations. For comparison only, inherited values declared by the engine's vertical-span metadata are suppressed to match the anchor-only annotation. Exports retain shared values and provenance. This policy is explicit in the manifest and each report; raw exported values are not claimed identical to anchor-only annotations.

Other normalization changes whitespace only. Extra/missing cells, ordered positions, table counts and headers matter. This is **not held out**: the first case prompted a fix. These three PDFs add external layout coverage, not an unbiased performance estimate.

## Reproduce and inspect

- `START_DAMNLENS.cmd --judge-test --offline` / `sh start.sh --judge-test --offline`: eight runtime checks after first setup: three sample workbooks, nested structure, split-row evidence, 50-page duplicates, 51-page rejection and interrupted recovery.
- `python -m pytest -q`: 150 extraction/API/review/export/recovery/cloud-contract tests; JUnit in `reports/tests.xml`.
- `python scripts/benchmark.py`: original sample workbooks, `reports/benchmark.json` and `ACCURACY_REPORT.md`.
- `python scripts/judge_audit.py`: 15 varied cases; historical before/after JSON reports remain available.
- `python scripts/complex_evaluation.py`: 16 bundled complex PDFs, JSON and Excel in `evaluation/complex/`; report `reports/complex-evaluation.json`; original twelve-case baseline `reports/complex-before.json`.
- `python scripts/public_evaluation.py --fetch`: download/verify pinned public PDFs and write `reports/public-evaluation-final.json`. Omit `--fetch` for cached offline files. First-pass and glyph-fix reports are preserved.
- `docs/screenshots/18-checkpoint-recovery.jpg` through `22-nested-header-groups.jpg`: actual restart, resume log, source-part, evaluation and nested-origin screens.
- [GitHub Actions](https://github.com/rayanakarthikeyan/damnlens-ai-agent/actions): Windows/Ubuntu tests, fresh setup, offline smoke checks and public-fixture comparisons.

## Remaining risks

Unseen nested/ragged structures, changing schemas, dense footnotes, missed secondary tables, severe blur, handwriting and other OCR languages remain risks. Shared values, recovered glyphs, inferred alignment and cross-page joins require visible source review. No cloud LLM is required; document content is never an executable instruction. The demo is a 150-second captioned walkthrough of real screens, not an uncut speed recording. AI assistance is disclosed. Entrant details, eligibility interpretation and the real submission link remain the entrant's responsibility.
