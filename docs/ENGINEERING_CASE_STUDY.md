# DamnLens engineering case study

DamnLens turns digital PDFs and scanned tables into Excel workbooks while retaining the source needed to review the output. The engineering problem is preserving correct data and review state when extraction is uncertain or interrupted.

## Implementation

- Python/FastAPI API and browser review workspace; local pretrained OCR with optional Gemini assistance.
- Native extraction or OCR, conservative cross-page table stitching, and decimal-based financial validation.
- Page checkpoints let an interrupted job resume verified pages. Changed input bytes or extraction mode invalidate the checkpoints.
- A review is bound to a data fingerprint. Editing extracted values revokes that review; the export carries its current review state.
- Excel output stores source strings as text, and CSV export neutralizes formula-leading values.

See [the extraction engine](../app/engine.py), [checkpoint persistence](../app/checkpoints.py), [review assessment](../app/quality.py), and [export formats](../app/exporter.py).

## Reproduce the evidence

After installing `requirements-dev.txt` with Python 3.12:

```sh
python -m pytest -q
python scripts/benchmark.py --check --output-dir reports/portfolio-benchmark
```

The benchmark compares three authored synthetic documents with their exact ground truth. It reports normalized cell accuracy, exact-row multiset recall and precision, header equality, and elapsed extraction time. Added or missing rows are penalized. `--check` exits nonzero if any fixture is incomplete or incorrect, including incorrect headers or an empty result set. Generated workbooks and reports stay in the requested output directory.

The [recorded local run](../reports/portfolio-benchmark/benchmark.json) on 21 October 2026 matched 864/864 expected cells, all 72 expected rows, and all three headers across seven pages. These are the same three authored development fixtures, not unseen documents. Re-run the command to evaluate a later change; timings in that report are single-run observations on its stated environment.

[Benchmark gate regressions](../tests/test_benchmark_gate.py) deliberately exercise incorrect cells, missing rows, extra rows, incorrect headers, an empty evaluation, and CLI failure propagation. [Checkpoint tests](../tests/test_checkpoints.py) interrupt processing and corrupt cached pages. [API tests](../tests/test_api.py) check that corrections invalidate review before export.

The [GitHub Actions workflow](../.github/workflows/test.yml) runs the fixture gate and test suite on Linux, Windows, and macOS, retains reports, and separately checks container execution and public PDF fixtures. Inspect the linked run and artifact for the exact commit rather than assuming a previous green run covers later changes.

## What the result means

The bundled fixtures are a reproducible regression cohort, not an independent estimate of accuracy on arbitrary documents. OCR confidence is not extraction accuracy. Layout and recognition can still fail; human review remains part of the workflow. The optional provider path has separate evaluation limits, and this case study does not claim model training, a hosted research API, or production throughput.

## Interview walkthrough

Demonstrate a fixture, inspect an extracted cell beside its source, complete review, change the cell, and show that review becomes pending. Then interrupt a multi-page extraction and explain why only verified checkpoints can be reused. Discuss the trade-off between conservative stitching and losing ambiguous continuation candidates.
