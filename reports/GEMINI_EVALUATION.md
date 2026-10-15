# Gemini-assisted workflow: live checks and limits

Tested 15 October 2026 with the user-authorized key, held only in test-process memory. No key is included in source, reports, screenshots, jobs or submission. Model: `gemini-3.8-flash`; maximum one request and 8,192 output tokens per experiment. Real requests used the same transport/schema/comparison code as the application. Separate unit/API tests mock cloud responses and need no key.

## Observed results

| Experiment | Input sent | Provider outcome | Checked data cells | Headers | Local result retained |
|---|---|---|---|---|---|
| [Invoice, first page](gemini-live-01_invoice_register.json) | One-page native PDF | Completed | 120/120 | 12/12 | All 31 local rows |
| [Scan, initial attempt](gemini-live-02_scanned_inventory-first-attempt.json) | One-page image-only PDF | HTTP 503; stopped | No cloud reading | Not evaluated | All 20 local rows |
| [Bank statement, first page](gemini-live-03_bank_statement.json) | One-page native PDF | Completed | 120/120 | 12/12 | All 21 local rows |
| [Scan, browser attempt](gemini-live-02_scanned_inventory-pdf-ui-attempt.json) | One-page image-only PDF | HTTP 503; stopped | No cloud reading | Not evaluated | All 20 local rows |
| [Scan, revised browser route](gemini-live-02_scanned_inventory.json) | Full page rendered as 180-DPI PNG | Completed | 120/120 | 12/12 | All 20 local rows |

**Five request attempts: three completed, two provider failures.** Completed readings matched **360/360 checked data cells and all 36 headers**. Provider-reported total tokens for completed requests: **7,586**, including reported thinking tokens. Failed requests had no reported usage; billing cannot be inferred from this count. No general availability percentage is claimed from five attempts.

Two scan-PDF attempts returned 503 while digital PDFs worked. The revised scan route sends a bounded full-page PNG directly, avoiding PDF image-container interpretation; its live browser reading succeeded. This evidence motivated a separate media route for OCR pages. It does not establish that every 503 has this cause or that future requests will always succeed. The application still stops on failure and retains local results; it never automatically switches billable models or retries.

## Methodology and scope

All documents are the original fictional fixtures already supplied with this project. **Only page 1 of each was cloud-transcribed**, with exactly ten rows and twelve columns in the generator. Compare ordered strings against the first ten rows of `samples/ground_truth.json`, normalizing whitespace only. Denominator penalizes missing/extra cells; table count, shape and exact headers are reported separately. The bank page includes a deliberately missing debit and altered balance; both were faithfully preserved. Its page-two total error was outside this live check.

The complete local documents were still extracted and validated: 31 invoice rows, 20 inventory rows and 21 bank rows. Candidate readings never silently replaced a local cell. In the browser scan run, the one-request limit visibly skipped page 2 and produced an incomplete-assistance finding. Successful transcription of page 1 did not mark the whole document cloud-verified.

These are small, non-blind development smoke checks. The local readings already matched these fixtures, so this experiment demonstrates **live compatibility, source preservation and failure recovery**, not an accuracy improvement over local AI. It establishes no score, hidden-PDF accuracy, multilingual/handwriting support or general Gemini reliability.

## Reproduce

Configure your own `GEMINI_API_KEY` in the launch environment or ignored `.env`, then run:

```bash
python scripts/gemini_evaluation.py --allow-cloud --sample 01_invoice_register
python scripts/gemini_evaluation.py --allow-cloud --sample 02_scanned_inventory
python scripts/gemini_evaluation.py --allow-cloud --sample 03_bank_statement
```

Each command authorizes at most one new request on a dummy first page. Repeating it is a new experiment and may incur another charge; these live smoke commands intentionally have no resume ledger. A private hidden prompt is available with `--key-stdin` in a terminal. Normal CLI conversions persist their ledger beside the output; web jobs keep it inside the job folder.

To test the real UI: select Gemini-assisted AI, Difficult pages first, request limit 1, authorize cloud processing, then upload the dummy scan. Inspect **AI workflow** and export its JSON/Excel. Recorded screens show a real failure and the revised completed reading; no cloud results were fabricated for screenshots. General local cohorts and residual failures remain in [JUDGE_EVALUATION.md](JUDGE_EVALUATION.md) and [EXPANDED_EVALUATION.md](EXPANDED_EVALUATION.md).
