# Two workflows, shared integrity

Both modes use AI: Local AI uses bundled pretrained English OCR; Gemini-assisted AI adds an independent multimodal reading. Local is the keyless, offline-after-setup default for judges. The README contains a visual architecture diagram and setup instructions.

## Workflow and trust boundaries

1. Choose a mode before upload. Gemini requires a server-side key, page scope, request limit and explicit cloud authorization. Sample fixture buttons always run locally.
2. FastAPI enforces file type, 40 MB, encryption and 1–50 pages. A persistent single-worker queue runs native extraction/OCR fallback, column reconstruction, conservative stitching and deterministic validation. Verified local checkpoints support interruption recovery.
3. Local AI proceeds to review. Gemini selects scanned/uncovered pages, findings and inferred/hierarchical headers. All-pages scope is available. The difficult-page heuristic can miss clean-looking errors.
4. Persist a request reservation, create a single-page PDF for native text or a 180-DPI PNG for OCR pages in memory, then call Google's fixed HTTPS endpoint. Keys are headers, never URL parameters. No tools, URL fetching, code execution or document instructions are enabled. Maximum 8,192 output tokens, 60-second socket timeout and 1–50 request reservations (default 3).
5. Accept only a completed `STOP` response. Check JSON size, exact keys, rectangular string cells, table/row/column/cell limits and nonnegative usage counts. Schema validity is not transcription truth.
6. Preserve independent candidate tables. Map a proposal only when page table order, normalized headers and row counts match, exactly one cell differs, and remaining row anchors are unique in both readings. Punctuation is preserved in comparison. Duplicates, reordered rows, cross-page parts, header changes and extra/missing rows or columns become structural findings. No automatic model-driven joins, deletions or replacements.
7. Both paths converge on original-source review. **Inspect & edit** opens a mapped proposal in the existing correction dialog. Users decide whether to save. Every correction preserves the prior value, reruns deterministic checks and revokes the earlier review. Unmapped structural differences require manual reconstruction; cloud mode does not automatically rescue arbitrary missing tables.
8. Main Excel tables contain local extraction plus explicitly saved corrections. Overview records workflow/model/request/token metadata. **Gemini candidates** and JSON preserve unverified readings separately; candidate strings are literal text, including `=` prefixes. Source geometry, validation, events and review history remain available. Model agreement is not ground truth.

## Cost, data handling and recovery

| Situation | Behavior |
|---|---|
| Local selected, no key/internet | Full local workflow available after installation; no AI API requests. |
| Gemini without key/authorization | Rejected before job creation; UI explains setup or local selection. |
| No qualifying page | Zero cloud calls; source review still required. |
| Selected pages exceed budget | Remaining pages visibly skipped; local extraction still covers all input pages. |
| Quota, key error, network failure, blocked/invalid output | Stop cloud processing; retain local result and record incomplete assistance. |
| Restart during a request | Reservation becomes unknown, counts against limit and is not resent; it may have been charged. |
| Restart after completion | Matching baseline/config reuses saved candidates without another request. |
| Changed baseline/config | No silent fresh cloud budget; new opted-in extraction required. |
| Retry OCR | Fresh local OCR; previous completed results archived. |

Local has no API fee/provider quota, while hardware, electricity, storage and input limits remain. Gemini offers free and paid tiers depending on model/account/region. Available token usage is reported; failed requests can have unreported cost. A request cap is not a currency cap. No price or free-tier entitlement is assumed.

Selected **full pages** go to Google and may include surrounding text/images. Google's tier-specific API data terms apply. Keys come from the launch environment or ignored `.env`, never job data, exports, logs or browser storage. `.env` is a local plaintext credential file. Jobs and cached cloud readings persist locally until deleted. The localhost app has no multi-user authentication.

## Requirements and rubric mapping

| Requirement / rubric | Implementation and evidence |
|---|---|
| PDFs up to 50 pages | Shared preflight; 50-page duplicate-preservation and 51-page rejection tests. Cloud budget is separate from input length. |
| 10+ columns | Shared layout/stitching/export; three original 12-column PDF/Excel pairs. Model schema allows up to 60 candidate columns. |
| Scans and OCR / 30 marks | Bundled PP-OCRv3/v5, orientation/deskew, confidence findings and bounded retries; optional independent Gemini reading. Local cohorts and the three-page live cloud smoke check stay separate. |
| Headers, complex/multi-page tables / 25 | Grouped headers, explicit spans, borderless inference, independent continuations and split-row provenance. Complex development cohort: 16/16 cases, 962/962 checked cells. |
| Alignment and integrity / 20 | Decimal totals/balances, blanks/types/duplicates, source geometry, conservative proposals, safe Excel and human correction. No fabricated figures. |
| Automation/recovery / 15 | Native/OCR routing, queue, verified checkpoints, archived retries, bounded cloud calls, no resend of unknown billable requests and local fallback. |
| Quality/usability / 10 | One-command setup, keyless judge path, explicit workflow/cost controls, CLI/API, readable UI, pinned local dependencies and Windows/Ubuntu CI. |
| Submission | README maps app/source/setup, three PDF/Excel pairs, accuracy report, 222-second live application recording and credits. |

The current rubric estimate is 96/100 after the [code-quality audit](../reports/CODE_QUALITY.md); adding Gemini alone did not increase it. This remains subjective. No hidden-PDF or 100/100 guarantee is made. Severe damage, handwriting, multilingual OCR and arbitrary changing/nested schemas remain risks.

## Verification

`python -m pytest tests/test_gemini.py tests/test_api.py -q` covers local isolation, consent/configuration, schema rejection, HTTP errors, secret handling, single-page requests, budgets, duplicate ambiguity, preserved originals, candidate formula safety, review fingerprints and recovery. **Cloud responses are mocked; no API key or charges are needed.**

**Live checks completed:** three original dummy first pages matched 360/360 data cells and all 36 headers. Two earlier scan-PDF requests returned HTTP 503; the revised PNG route succeeded. Failures remain published in [the live evaluation](../reports/GEMINI_EVALUATION.md). These checks establish basic compatibility, not an accuracy uplift or hidden performance. Repeat with your own key via `python scripts/gemini_evaluation.py --allow-cloud --sample 02_scanned_inventory`; each invocation can make a new billable request.

Official references checked 15 October 2026: [PDF understanding](https://ai.google.dev/gemini-api/docs/document-processing), [structured outputs](https://ai.google.dev/gemini-api/docs/structured-output), [REST API](https://ai.google.dev/api/generate-content), [default model](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash), [pricing](https://ai.google.dev/gemini-api/docs/pricing), [terms](https://ai.google.dev/gemini-api/terms). Availability, prices and terms can change.
