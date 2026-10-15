# Maintaining DamnLens AI Agent

Judges only need the Python setup in README. The tools below are for source changes; the app has no frontend build step, Node.js runtime dependency or mandatory cloud key.

## Developer checks

Use 64-bit Python 3.12 and Node.js 20 or newer:

```bash
python -m pip install -r requirements-dev.txt
npm ci --ignore-scripts
python scripts/check_quality.py
python -m pytest -q --junitxml=reports/tests.xml
```

`check_quality.py` runs the same gates as CI: Ruff lint (including unused code, import order and common bug checks), Ruff formatting, JavaScript syntax and Prettier for all frontend source. Dependencies are pinned; npm has a lockfile. Format intentional changes with `python -m ruff format .` and `npm exec prettier -- --write web`. Direct `python scripts/...` entry points need repository-path bootstrapping; only the affected app imports carry a documented E402 exception. There are no directory-wide lint suppressions.

Tests isolate jobs under `tmp/pytest` and override `DAMNLENS_DATA`, including when your launch environment points to existing data. Fixture source documents are fictional/public. Gemini transport is mocked in automated tests: no API key, network billing or live cloud transcription is required. Live evaluation commands are a separate opt-in experiment, documented in `reports/GEMINI_EVALUATION.md`.

Run the affected tests while editing, then the full suite for extraction, persistence or API changes. Do not add tests that merely repeat an implementation or assert formatting strings. Use independent expected values and realistic failures: ordered cells, duplicate multiplicity, wrong totals, output collisions, interrupted requests and failed disk writes. Never loosen a golden result just to make a test pass. Preserve first-pass reports and disclose annotation corrections.

## Code boundaries and contracts

| Module | Responsibility |
|---|---|
| `engine`, `layout`, `ocr_verify` | Local recognition, geometry, conservative reconstruction, stitching and data validation |
| `workflow`, `gemini` | Explicit workflow choice, bounded second reading, schema checks and unverified proposals |
| `storage` | Atomic strict-JSON writes, unique temporary files, bounded Windows replacement retries and cleanup |
| `checkpoints` | Source/configuration signatures and checksums for completed local pages |
| `quality` | Observed coverage and snapshot-bound human review |
| `exporter` | Typed literal-safe Excel, source evidence and separate candidate readings |
| `main` | Local API, input limits, persistent queue and serialized job updates |
| `web` | Accessible browser controls and source-linked review, without a frontend build |

Preserve original values and evidence. Do not fill missing financial values through arithmetic, delete legitimate duplicate rows, silently replace data with LLM proposals, or interpret OCR confidence as accuracy. Candidate content is untrusted data. All changes to reviewed data must invalidate the review fingerprint. Validate external payloads at their boundary and keep provider errors free of credentials.

Use `app.storage.atomic_json` for jobs, checkpoints and cloud ledgers. It preserves the previous JSON on serialization/write/replace failure and does not mask the original exception during cleanup. The web lock serializes read/modify/write operations; atomic replacement alone is not a multi-process lock or power-loss guarantee. Run one process per cloud ledger. Persist a reservation before any billable request and never resend unknown requests automatically.

CLI Excel output must end in `.xlsx`. Source, workbook, optional JSON sidecar and Gemini ledger must have distinct resolved paths. A path error must be rejected before extraction or any cloud request. File errors should give an actionable exit message.

## Portability and UI verification

CI runs the extraction/API/recovery suite, fresh bootstrap, offline judge checks and pinned public-document evaluations on Windows, Ubuntu and macOS. A separate Ubuntu job builds the Docker image, verifies its non-root user and excluded dummy `.env` credential canary, then converts all three sample documents through the real container API and checks exact values, headers and valid Excel. CI artifacts retain the observed results; a configured job is not evidence of success until it passes.

To reproduce Docker verification with Docker installed:

```bash
docker build -t damnlens-check .
docker run -d --name damnlens-check -p 127.0.0.1:8765:8765 damnlens-check
python scripts/container_check.py
docker stop damnlens-check
docker rm damnlens-check
```

Review the browser after UI changes. Result tabs support Left/Right, Home and End, one Tab-stop for the selected tab, and labelled ARIA panels. Verify source navigation, cell editing, validation, export, large text and cloud authorization. Save real screenshots for visible changes; never fabricate extraction results. This keyboard support is not a formal accessibility certification.

## Release checklist

1. Pass static checks and affected/full regressions; confirm the relevant CI jobs are green.
2. Keep README setup, supported platforms, cost/data handling and measured limitations accurate. Update the demo only when its captured behavior changes materially.
3. Credit libraries, APIs/models and assistance. Never include a real key, `.env`, document job folder, virtual environment or temporary build data in Git, Docker context or the submission ZIP. `.env.example` is the empty configuration template.
4. Create the submission ZIP from the intended commit with `git archive`, then inspect required PDF/Excel pairs, models, reports and launchers. Judge scores remain estimates; new quality gates do not establish hidden-PDF accuracy.
