# Code quality and judge usability audit

**Provisional code-quality/usability estimate: 10/10.** The changes below close the remaining tooling, portability and usability gaps identified in the previous nine-mark estimate. This is a readiness assessment, not an organizer's score or a hidden-document accuracy measurement.

## Improvements

- **Enforced checks:** pinned Ruff lint/import/bug rules and formatting across the Python source; pinned, locked Prettier for frontend source; JavaScript syntax checking. `python scripts/check_quality.py` reproduces the CI quality gate. These maintenance tools add no Node.js requirement to the judge's Python application.
- **Shared persistence:** jobs, local page checkpoints and Gemini ledgers use `app/storage.py`. Strict JSON serialization, unique temporary files, bounded Windows retries and cleanup preserve the previous file on failed writes. Regression tests exercise full-disk, permanent-lock and non-finite-data failures. Atomic replacement is not a cross-process lock or power-loss guarantee.
- **Protected CLI outputs:** source, Excel, optional JSON sidecar and Gemini ledger cannot share a resolved path. Collisions are rejected before extraction or a cloud request. Excel output requires `.xlsx`; disk errors exit with an actionable message. This closes a collision that could overwrite a cloud reservation ledger with a JSON result.
- **Safe test isolation:** API tests override the current `DAMNLENS_DATA` setting. A launch environment pointing at existing maintainer data no longer redirects tests into that data folder. A separate configured-directory canary check passed without changing its contents.
- **Deployment hygiene:** Docker excludes `.env` and `.env.*` while keeping the empty `.env.example`. CI builds with a dummy credential canary, verifies the canary is absent from the non-root image, then exercises real extraction and export through the container API.
- **Keyboard review:** result tabs implement Left/Right wrapping, Home/End, one Tab-stop and labelled ARIA panels. Actual browser checks passed with large text and no console errors; [observations](code-quality-ui.json) and [screenshot](../docs/screenshots/33-keyboard-review.png) are recorded. This is focused keyboard QA, not accessibility certification.
- **Maintenance guidance:** [CONTRIBUTING.md](../CONTRIBUTING.md) describes module boundaries, data/review contracts, isolated tests, source preservation, cloud costs and release checks. README retains the simple judge setup, three PDF/Excel pairs and runnable demo.

## Verification

| Check | Evidence |
|---|---|
| Local Python lint/format and frontend syntax/format | Passed; 38 Python files checked, all frontend files formatted |
| Local full regression suite | 158 tests passed; [JUnit](tests.xml) |
| Configured-job-directory isolation | 16 API tests passed with an external data-folder canary unchanged |
| Browser keyboard/large text review | Passed; one selected Tab-stop, matching ARIA panels, no console errors |
| Non-root Docker, key exclusion and three sample conversions | Passed; [container artifact](container-check.json), 864/864 sample cells, exact headers and valid Excel |
| Windows, Ubuntu and macOS full CI | All passed: 158 tests per platform, zero failures/errors/skips; fresh setup, offline judge checks and public evaluations also passed |

Source verification run: [GitHub Actions 38715554376](https://github.com/rayanakarthikeyan/damnlens-ai-agent/actions/runs/38715554376), commit `c8d8b2be6793cafb5112e6a95684937c8ecacfd9`. All five jobs passed. The [saved CI summary](code-quality-ci.json) records each job and independently checked JUnit counts from all three platform artifacts. macOS and Docker were verified in CI; interactive browser QA was performed on Windows.

The extraction assessment is separate. The expanded cohort still has one explicitly flagged OCR-header mismatch, and unfamiliar layouts remain uncertain. Tooling, portability and usability improvements do not turn development fixtures into a blind benchmark.
