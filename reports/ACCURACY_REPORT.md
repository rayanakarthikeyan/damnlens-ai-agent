# Accuracy and validation report

Generated: 2026-10-15T06:05:51.831148+00:00

Compare normalized whitespace in every output cell to independently generated source ground truth in original row order. Cell accuracy divides matching cells by the larger of expected and actual cell counts, penalizing dropped and extra cells. Row recall and precision use exact full-row multiset matches, preserving duplicate multiplicity. Header equality is reported separately. Source errors count as correct only when faithfully preserved.

| Fixture | Pages | Matching cells | Cell accuracy | Exact row recall | Headers | Seconds |
|---|---:|---:|---:|---:|---|---:|
| 01_invoice_register.pdf | 3 | 372/372 | 100.00% | 100.00% | True | 0.25 |
| 02_scanned_inventory.pdf | 2 | 240/240 | 100.00% | 100.00% | True | 13.82 |
| 03_bank_statement.pdf | 2 | 252/252 | 100.00% | 100.00% | True | 0.18 |

## Validation findings

- **01_invoice_register.pdf:** 0 findings: {}.
- **02_scanned_inventory.pdf:** 0 findings: {}.
- **03_bank_statement.pdf:** 6 findings: {"missing_value": 2, "balance_mismatch": 2, "sparse_row": 1, "total_mismatch": 1}.

## Practical limits

Only three original, English, synthetic fixtures; clean scans at 150 DPI and consistent layouts. Results do not establish accuracy on unseen PDFs, handwriting, merged cells, nested tables, complex borderless layouts or other languages. No hidden evaluation was performed.

Confidence scores from OCR are recognition confidence only, never measured accuracy. Native extraction uses 1.0 as a non-OCR marker, not an accuracy estimate. Human review remains necessary.

## Reproduce

`python scripts/generate_samples.py` then `python scripts/benchmark.py`. Test additional adversarial and boundary cases with `python -m pytest -q`.

Synthetic fixtures were authored for this project with ReportLab; scans were rasterized with PyMuPDF. These metrics are transparent development checks, not a claim of independent third-party evaluation.
