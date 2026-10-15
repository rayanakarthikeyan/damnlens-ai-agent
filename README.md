# DamnLens AI Agent

**AI document extraction with source evidence and explicit review.** A local document-to-Excel agent for the INCUXAI AI Agent Development Challenge 2026.

DamnLens AI Agent reads digital PDFs and scanned documents, reconstructs tables, joins continuation pages, detects data problems and exports traceable Excel workbooks. The operational workspace shows the extraction queue, agent stages, page coverage and validation findings. Inspect original pages beside the extracted data, record corrections and complete a snapshot-bound review before labelling an export as reviewed.

![DamnLens AI Agent workspace](docs/screenshots/01-workspace-desktop.jpg)

## Judges: setup and launch

Requires **64-bit Python 3.12**, 4 GB RAM minimum (8 GB recommended), and network access for the initial Python dependency installation. A CPU is sufficient. No API key, GPU, Tesseract installation, subscription or model download is needed at runtime. The English model is included in `models/`.

```bash
git clone https://github.com/rayanakarthikeyan/damnlens-ai-agent.git
cd damnlens-ai-agent
```

**Windows:** extract the complete repository ZIP and double-click **START_DAMNLENS.cmd**. Keep the console open while testing. It checks the bundled model, creates a local environment if needed, installs pinned dependencies once, then opens the workspace. No PowerShell policy change is needed.

Windows command line:

```powershell
.\START_DAMNLENS.cmd
```

macOS / Linux:

```bash
sh start.sh
```

The launcher prints and opens the local URL. It starts at **http://127.0.0.1:8765**, choosing the next free port if necessary. The browser opens after server readiness. Press Ctrl+C to stop. Subsequent launches work offline when all dependencies are present.

**One-command judge checks:** `START_DAMNLENS.cmd --judge-test --offline` (Windows) or `sh start.sh --judge-test --offline` (macOS/Linux), after initial setup. Eight checks cover all three PDF/Excel pairs against exact truth, nested line items, cross-page source parts, duplicate records through 50 pages, 51-page rejection and checkpoint recovery. Failure returns a nonzero exit code; results go to `reports/judge-check-latest.json`. No development libraries are required.

**Diagnostics only:** `START_DAMNLENS.cmd --check --offline`, or `python setup_judges.py --check`. **Install without launching:** `python setup_judges.py --setup-only`. Add `--no-browser` or `--port 8786` to the launcher as needed. The UI's **Text size → Large** setting increases all text by 12.5% and persists on this browser. Standard mode uses 13px minimum secondary labels, 14px data cells and 15px explanatory text with stronger contrast; normal browser zoom also works.

If script execution is restricted on Windows, use the manual commands below rather than changing your system policy. On Linux, OpenCV may require `sudo apt-get install libgl1 libglib2.0-0`; Python virtual environments may require the `python3-venv` package. macOS dependencies are supplied as Python wheels on supported systems. Windows is locally verified; Linux is covered by the included CI workflow when GitHub Actions is available.

### Manual setup

```bash
python -m venv .venv
# Windows:
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python run.py
# macOS / Linux:
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py
```

Use `python run.py --no-browser --port 8766` inside the activated environment to change the port or skip opening a browser. Initial OCR initialization can take several seconds. Large scanned documents take longer; page progress remains visible. Only one extraction runs at a time to keep model memory bounded.

### Headless judging

```bash
python convert.py samples/01_invoice_register.pdf -o result.xlsx --json
python convert.py scan.png -o scan.xlsx --force-ocr
```

Exit code 0 means conversion completed, 1 means a fatal error and 2 means no tables were extracted. Findings do not make the CLI fail: source errors are preserved in the output and listed on the Validation sheet. Check that sheet before using the data.

### Docker alternative

```bash
docker build -t damnlens-ai-agent .
docker run --rm -p 127.0.0.1:8765:8765 -v damnlens-data:/data damnlens-ai-agent
```

The container runs as a non-root user. The Dockerfile is supplied for portability; local Windows Python execution is the directly verified setup.

## What the agent does

1. **Inspect:** validate the file and the 1–50 page limit; inspect each page for usable native text.
2. **Extract:** detect ruled native tables with PyMuPDF. For borderless text, group headers and anchor columns to their positions. Retry with OCR when native extraction fails or produces no tables.
3. **Recognize:** rasterize scans at 220 DPI, recover right-angle scan orientation, deskew modest scan angles, recognize text locally using RapidOCR with the English PP-OCRv3 model, reconstruct grid cells using OpenCV, and anchor borderless values to detected headers. Empty grid cells with visible ink get a local OCR retry. PDF rotation is normalized for extraction while evidence stays aligned with the original page. A sparse group heading above real column labels is handled separately.
4. **Stitch:** match eligible table streams on adjacent pages using conservative header and horizontal-span checks. Two different tables can each continue across the same pair of pages. Headerless continuation requires matching column counts and horizontal spans. Repeated page headers are removed. Identical business rows are preserved and flagged, never silently deduplicated.
5. **Validate:** check totals/subtotals, quantity × unit price, net + tax, running bank balances, numeric type inconsistencies, empty columns, missing values, sparse rows, duplicate rows, low OCR scores and pages with no detected table. Financial checks use decimal arithmetic and a half-cent rounding tolerance; large totals do not get a looser relative tolerance. Borderless alignment gets an explicit review finding.
6. **Review and export:** preserve row evidence, record corrections, rerun validation and maintain a separate human review state. Export Excel, JSON or CSV. Draft exports remain labelled unreviewed; completing review records the exact data fingerprint and any acknowledged findings. A correction invalidates the review and retains its prior decision in history.

This is a bounded agent workflow with an explicit inspect → extract → retry → stitch → validate → review lifecycle. It uses pretrained ML for recognition and deterministic layout/validation logic. It does not call an LLM or claim to train an OCR model.

## Review workspace

- Professional operational UI: live run queue, real counts, search/status filters, cross-document review inbox, agent stages, page coverage, timestamped execution log and sample fixtures.
- Digital PDF, PDF scans, PNG, JPEG, TIFF, BMP and WebP input; up to **50 pages / 40 MB** per web upload. Multi-frame TIFF behavior depends on PyMuPDF; use PDF for multi-page scans.
- Side-by-side original page, highlighted row evidence, table navigation and Excel export.
- Validation findings link directly to the corresponding row.
- Double-click a cell or focus it and press Enter to edit. The original value remains in the correction history.
- Retry with forced OCR for PDFs with broken text layers. Before reprocessing, a retry archives the prior run including corrections and review history. Download any previous run as Excel or JSON from the agent run log. Exports are blocked while a replacement run is pending, preventing stale data downloads.
- Source zoom, page navigation, flagged-row filtering, severity filters and correction history support source verification.
- Completing review requires a source-check confirmation. Outstanding findings also require explicit acknowledgement and a note. This is a human decision, not a measured accuracy guarantee.
- Source data stays under `.jobs/`, which is ignored by Git. The delete control permanently removes the selected local job. Do not delete a job whose source is your only copy.

## Deliverables and measured results

| Deliverable | Location |
|---|---|
| Working application and source | `app/`, `web/`, `run.py`, `convert.py` |
| Setup and run instructions | This README; `START_DAMNLENS.cmd`, `setup_judges.py`, `start.ps1`, `start.sh`, `Dockerfile` |
| Three original sample PDFs | `samples/01_invoice_register.pdf`, `02_scanned_inventory.pdf`, `03_bank_statement.pdf` |
| Corresponding Excel workbooks | `samples/converted/` |
| Accuracy and validation report | [reports/ACCURACY_REPORT.md](reports/ACCURACY_REPORT.md) |
| Cell-level benchmark output | `reports/benchmark.json`, `reports/01_*.json`, `reports/02_*.json`, `reports/03_*.json` |
| Ground truth and regeneration | `samples/ground_truth.json`, `scripts/generate_samples.py` |
| Automated tests | `tests/`, `reports/tests.xml`, `.github/workflows/test.yml` |
| Short demo | `docs/damnlens-demo.mp4`, `docs/DEMO_SCRIPT.md` |
| Requirement mapping | [docs/SUBMISSION_CHECKLIST.md](docs/SUBMISSION_CHECKLIST.md) |
| Judge audit and rubric self-assessment | [reports/JUDGE_EVALUATION.md](reports/JUDGE_EVALUATION.md), `reports/judge-audit-before.json`, `reports/judge-audit-after.json`, `evaluation/pdfs/` |
| Library/model credits | [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), `models/README.md` |

On the three included English synthetic fixtures, **864 / 864 data cells** and all headers match ground truth. The scanned fixture is image-only: 240 / 240 cells match. A separate automated 50-page test checks 501 rows × 12 columns and 49 removed repeated headers. These results describe this development set, not expected accuracy on arbitrary or hidden PDFs. Timings and raw comparisons are included in the report.

The v1.3 complex audit adds **16/16 exact cases and 962/962 cells**: multi-line/hierarchical headers, true vertical merges, nested child tables, cross-page descriptive row parts, distinct account sections and intentional blank cells. Full header paths, inherited-cell geometry and continuation parts survive JSON/Excel export. Clicking a shared cell highlights its original merged rectangle; continued rows expose each source-page part. Reconstructed structure remains flagged for source review.

A separate public-fixture comparison matches **261/261 cells across three digital PDFs**, using independent Camelot annotations and an explicit anchor/shared-value policy. It was used for development, so it is not a blind evaluation. Run `python scripts/complex_evaluation.py` for the bundled complex cases, or `python scripts/public_evaluation.py --fetch` for pinned public downloads. See [the judge evaluation](reports/JUDGE_EVALUATION.md), raw JSON reports, `evaluation/complex/` PDF/Excel pairs and `evaluation/public/manifest.json`. The complete suite has **100 tests**.

The bank fixture deliberately contains a wrong debit total, an altered running balance, a missing debit and missing currency. Faithful extraction preserves these errors; validation flags them. A changed balance can produce two transition warnings because it affects both the row's incoming and outgoing balance checks.

### Excel output

Each workbook contains **Overview**, one sheet per joined **Table**, **Validation**, **Evidence**, **Corrections**, **Page coverage**, and **Run log**. Overview records draft/reviewed status, review time, accepted findings and the review note. Amounts, dates and percentages are typed; identifiers and leading zeros remain text. Source decimal precision is retained. Values exceeding Excel’s 15-digit numeric precision remain text. Tables have filters, frozen headers, readable widths and warning highlights. Row evidence includes the source page and bounding box in PDF points. Source text beginning with `=` is stored as text, never as an executable formula. CSV formula-like values are escaped.

The expanded regression suite includes same-schema table-position matching, real multi-table PDFs, snapshot-bound review, prior-run recovery, precision-preserving exports and 15 differently styled document cases. The development audit improved from **5/15 to 15/15 exact cases** after targeted fixes. The new documents are regression fixtures used during development, not an independent hidden set. See the judge evaluation for the evidence and remaining gaps.

## Reproduce the evaluation

```bash
python -m pip install -r requirements-dev.txt
python scripts/generate_samples.py
python scripts/benchmark.py
python scripts/judge_audit.py
python -m pytest -q --junitxml=reports/tests.xml
```

The benchmark compares cells in original row order and penalizes extra/missing cells. Exact-row precision/recall compares full-row multisets, including duplicate multiplicity. Header equality is checked separately. Source validation mistakes are not extraction mistakes when faithfully preserved. OCR scores are model recognition confidence, not accuracy measurements. Native PDF rows have blank OCR-score cells in Excel; the JSON record retains its internal non-OCR marker.

Tests cover native tables, OCR, borderless multiword headers, page stitching, duplicate preservation, headerless continuations, the 50/51-page boundary, encrypted/corrupt/oversized files, numeric locales, subtotals, line arithmetic, bank errors, typed XLSX, formula injection, evidence, corrections, origin/host protection and restart recovery.

## Architecture

```text
Browser review UI ── FastAPI local API ── persistent job queue (single worker)
                                           │
                       inspect → native extraction → OCR fallback
                                           │
                         table fragments → schema stitching
                                           │
                      validation + row evidence + corrections
                                           │
                                  XLSX / CSV / JSON
```

`app/quality.py` computes observed quality facts and snapshot-bound human review; `app/engine.py` contains extraction, layout, stitching and checks; `app/exporter.py` contains typed/safe export; `app/main.py` owns file limits, jobs, persistence and API routes. `web/` is plain HTML/CSS/JavaScript, served locally with no CDN or frontend build step. API documentation is at `/api/docs`.

## Accuracy workflow (v1.1)

Extraction and review are separate states. The agent automatically routes pages, extracts tables, matches continuations and validates the result. A human checks source evidence and either resolves or acknowledges findings. A reviewed workbook is tied to a fingerprint of the source, data, findings, coverage and correction history; any subsequent data change resets review. The UI never represents OCR model confidence as measured extraction accuracy.

A review is a local workflow record; there is no authenticated reviewer identity or cryptographic signature. The source hash and review fingerprint are integrity aids.

## Practical limits and recovery

- Bounded multi-line/hierarchical headers, explicit merged spans, a nested line-item layout, rotations and modest skew are covered by development regressions. Arbitrary nested layouts, changing schemas, handwriting and heavily damaged scans may still need manual reconstruction. Printed English is the evaluated OCR target.
- Identical schemas can represent different sections; explicit account/invoice context helps keep them separate. Compatible streams can continue independently. Duplicate business rows are never dropped automatically. Initial description-only continuation fragments can join the prior identified row, retaining both source parts and a review finding; complicated or ambiguous page breaks still require inspection.
- Borderless detection is heuristic; a structured-looking result is not proof of correct column alignment. Pages without a detected table produce a page-level finding rather than disappearing silently. Unrecognized secondary tables on an otherwise extracted page may still require visual review.
- Totals are checked only where recognizable labels and numeric columns exist. Quantity, price, net and bank checks require matching headers. Not every business rule is inferable. Section totals sum since the preceding total; an explicitly labelled grand total sums all normal rows. Sparse total rows may themselves receive a sparse-row warning.
- The queue is single-process and persists source/status/results and completed-page checkpoints. On restart, unfinished jobs become interrupted. Resume reuses only pages verified against source, code, OCR mode/assets and library signatures; corrupt or mismatched checkpoints are recomputed. An interrupted current page restarts. There is no mid-page continuation, cross-process locking, cancellation, authentication or hosted multi-user service.
- Jobs contain local source copies and extracted data until deleted. The app binds to localhost, restricts host/origin, uses generated job paths and does not send documents to cloud services. It is a local judging app, not an internet deployment configuration.

### Setup troubleshooting

- **Python missing:** install 64-bit Python 3.12 from [python.org](https://www.python.org/downloads/), enable the Python launcher/PATH option, reopen the folder and start again. The setup script does not install system software.
- **Cannot download packages:** initial setup needs internet access to PyPI. Retry the launcher after restoring the connection. An incomplete installation is detected and retried; `--offline` refuses installation explicitly.
- **Linux OpenCV import error:** install `libgl1` and `libglib2.0-0`; `python3-venv` may also be required. Then rerun setup.
- **Damaged OCR asset:** download the complete ZIP or clone again. Diagnostics verify model/dictionary SHA-256 hashes before launching.
- **Port busy:** automatic launch tries ports 8765–8784; choose `--port 8786` if all are occupied. An explicitly requested occupied port produces an actionable error.
- **Recover after interruption:** restart and open the interrupted document. **Resume extraction** reuses verified completed pages using the original routing mode. **Retry OCR** starts a fresh OCR run. The original stays local, existing results are archived and export is unavailable during processing.

`DAMNLENS_DATA` selects an alternate job folder. The legacy `LEDGERLENS_DATA` variable remains a fallback for existing installations.

## Authorship and licensing

Created for **Rayan Karthikeyan**. Repository commits use **rayanakarthikeyan@gmail.com** as author and committer email. Coding assistance and all upstream libraries/models are credited in `THIRD_PARTY_NOTICES.md`; do not describe AI-assisted code as wholly unaided work. The application uses AGPL-3.0-or-later, with separately licensed upstream dependencies and model weights.

Competition deadline supplied in the brief: **16 October 2026, 7:00 PM**. The brief does not specify a timezone. The submission URL and organizer contact are placeholders; obtain the actual submission link and confirm the deadline timezone with the organizer. This repository does not submit to the competition automatically.
