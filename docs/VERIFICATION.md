# Verification record

Verified locally on Windows with Python 3.12.14.

- **51 automated tests passed**. The raw JUnit record is `reports/tests.xml`. One upstream Starlette warning advises moving its test transport to HTTPX2; it does not affect extraction or the running application.
- **864/864 synthetic fixture data cells match ground truth**, with exact headers and exact-row recall. See `reports/benchmark.json` and `reports/ACCURACY_REPORT.md` for methodology and limitations.
- **50-page stress test:** one joined table, 501 rows, 12 columns, all source cells preserved, 49 repeated headers removed.
- **Borderless regression:** two-page digital fixture preserves multiword headers and all data cells, with alignment marked for review.
- **Browser flow:** real invoice, scan and bank fixture extraction; row-to-source highlight on page 2; validation-to-row navigation; missing-currency correction; finding count changes from 6 to 5; one correction remains in history; Excel downloaded successfully.
- **Export inspection:** seven sheet types, draft/reviewed metadata, typed numbers/dates/percentages, source decimal precision, preserved identifiers/long values, filtered/frozen table data, matching evidence rows and text-only untrusted formula-like content.
- **CLI:** bank statement exported to Excel and JSON, with 21 rows and six source findings.
- **Visual inspection:** rendered sample PDFs inspected for legibility and table alignment. Desktop and mobile browser screenshots are in `docs/screenshots/`.
- **Video:** H.264 MP4, 1920 × 1080, 12 frames/second, exactly 150 seconds. Captioned walkthrough using real UI captures, not an uncut performance recording.
- **Static checks:** Python compilation and JavaScript syntax checks pass. Python and frontend sources are formatted for readability.

Windows and Linux CI results are visible under the repository's Actions tab. The previous release passed on both operating systems. Docker configuration is supplied but was not manually verified locally.

## Accuracy workflow audit (v1.1)

- The UI now presents a document queue, observed quality facts, an agent pipeline, exception inbox, source comparison, severity/flagged-row filters, page coverage and timestamped execution events.
- Review is explicitly separate from extraction completion and from OCR confidence. Completing review binds a decision to the data fingerprint. Outstanding findings require acknowledgement and a note; subsequent changes invalidate review and retain its prior decision. Saving an unchanged cell does not invalidate review.
- Browser verification: a bank fixture finding locates page 2 and the correct row; correcting missing currency reduces six findings to five; completing review retains those five accepted findings; the export modal clearly shows a reviewed decision with three errors and two warnings.
- Safe retry verification: the current corrected/reviewed run is archived before OCR retry. Tests verify prior-run Excel/JSON downloads and that a pending replacement run cannot export a stale result.
- Multi-table accuracy: a real two-page PDF with two separate continuing table streams produces two joined tables with both rows preserved in each. Similar wide schemas with different identity headers are kept separate.
- Numeric integrity: zero values, Indian grouping without decimals, source decimal precision and values beyond Excel's 15-digit numeric precision have dedicated regression coverage.
- Source documents and extracted content remain data, never executable agent instructions. Benchmark accuracy remains measured against explicit ground truth, not inferred from OCR scores.
