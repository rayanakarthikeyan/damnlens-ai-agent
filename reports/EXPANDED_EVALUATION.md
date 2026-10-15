# Expanded public PDF evaluation — v1.4

**Result: 3/11 checkpoint cases before repairs → 10/11 strict cases after.** One scanned header remains ambiguous and is explicitly flagged for source review. This is not a 100/100 judging score or a whole-document OCR accuracy measurement.

## Scope and reference data

Seven previously unevaluated public aggregate/dummy PDFs were selected from Camelot commit `92777b852e00933a5c4b9ba642601784604356cd`. Four additional image-only PDFs were rasterized from those sources at 180 DPI. They are scan derivatives, not independently collected physical scanner captures. Source URLs and SHA-256 checksums are in [the manifest](../evaluation/expanded/manifest.json); PDFs are downloaded to ignored temporary storage rather than redistributed.

The original expectations were recorded before the first DamnLens comparison. The background-table annotation came from Camelot's MIT-licensed test data; other checkpoints were transcribed from source text/geometry and reviewed against the rendered source. They are not independent third-party annotations. The outbreak audits check the first nine columns, excluding long comments; the survey audit checks three selected rows and the five-column schema. Other cases check full ordered data rows. All cases check table and column counts. These selected checkpoints must not be represented as whole-document cell accuracy.

Two annotation errors were identified on source reinspection: the background table's numeric cells visibly span Delhi and Rajasthan, whereas the upstream anchor-only annotation leaves Rajasthan blank; Umaria's reporting date and status were initially transcribed incorrectly. These are reference corrections, not engine improvements. [The initial manifest](../evaluation/expanded/manifest-first-pass.json) and [original first-pass report](expanded-before.json) remain intact. The 3/11 baseline [re-scores the original pre-repair outputs against the corrected annotations](expanded-before-corrected.json), without re-extracting them. After repairs, these cases are development regressions, not held-out hidden PDFs.

A candidate containing an individual medical record was excluded before agent testing to honor the challenge's no-personal-data rule. It is not included in the manifest, reports or submission.

## Results

| Case | Corrected baseline | Final strict result |
|---|---|---|
| Background lines, digital | Pass | Pass |
| Hierarchical headers with column-reference numbers, digital | Fail | Pass |
| Vertical row spans, digital | Pass | Pass |
| Multiple merged entities, digital | Pass | Pass |
| Unknown-label borderless table across two pages | Fail | Pass |
| Nested table inside a comment cell | Fail | Pass |
| Dotted-leader survey with empty columns | Fail | Pass, selected rows only |
| White grid on colored cells, image-only | Fail | Pass |
| Hierarchical/reference-number table, image-only | Fail | **Header review required** |
| Numeric/shared row spans, image-only | Fail | Pass |
| Unknown-label borderless table, image-only | Fail | Pass |

The remaining case has the correct 47 × 8 shape and all **376 checked data cells**. The primary OCR reads `SI. No.`; the expected header is `Sl. No.`. Secondary readings disagree, so the original reading is retained and a header-level `ocr_disagreement` finding survives JSON, Excel Structure/Validation sheets and the review UI. The live app showed 47 rows, one warning, complete row evidence and a 99.8% mean recognition score: that high score did not suppress the warning.

## Repairs

- Preserve complete external header words, infer unfamiliar schemas from repeated aligned numeric rows, remove dotted leaders as layout separators, and retain truly empty columns.
- Keep sequential `(1)…(N)` column references in header context rather than data rows; preserve hierarchical paths.
- Reject a nearby prose line as a nested table's header and remove header-only output tables. Pages with no remaining data correctly require review.
- Detect white/partial rulings, reject boxed prose, recover numeric vertical spans from explicit geometry and flag inferred repairs of broken separators.
- Cluster text baselines before x-ordering to avoid moving words between lines inside long cells.
- Add a bundled, checksum-verified PP-OCRv5 English recognizer for bounded checks of short ambiguous labels. Two-scale agreement above 0.90 can change a reading; disagreement retains the original and requires review. No expected values or source filenames enter the extraction logic.
- Distinguish totals over unique merged source amounts from totals over expanded logical rows. Both interpretations are shown for review; an amount matching neither still produces an error. Repeated independent source records remain counted.
- Invalidate checkpoints when verifier code or model assets change; preserve uncertainty metadata in viewer coordinates and exports.

## Verification and reproduction

The local suite passed **115 tests**, including 15 new structural, geometry, OCR-consensus, header-provenance and merged-total regressions. The original three samples remain **864/864** cells; the original public fixtures remain **261/261** under their disclosed policies. All eight offline judge checks pass. The existing 16-case complex corpus remains covered by the regression suite. Windows/Ubuntu CI reruns the full suite, fresh setup, offline checks and both public evaluations.

```bash
python scripts/expanded_evaluation.py --fetch
```

The default strict command returns a failure code while the header mismatch remains. Omitting `--fetch` uses the verified cached sources offline. CI uses `--check-review-routing`: only a sole header-text mismatch accompanied by a recorded OCR disagreement is accepted as a safe review outcome; unexpected data, shape, table-count or unflagged-header failures still fail. [The saved report](expanded-after.json) always retains the strict 10/11 count. Review routing is not extraction accuracy.

See [model provenance](../models/README.md), [fixture annotation license](../evaluation/public/CAMELOT_LICENSE.txt), and [GitHub Actions](https://github.com/rayanakarthikeyan/damnlens-ai-agent/actions). Arbitrary layouts, damaged scans, handwriting and unsupported languages remain outside a demonstrated perfect-accuracy claim.
