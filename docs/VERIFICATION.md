# Verification record

Verified locally on Windows with Python 3.12.14.

- **36 automated tests passed**. The raw JUnit record is `reports/tests.xml`. One upstream Starlette warning advises moving its test transport to HTTPX2; it does not affect extraction or the running application.
- **864/864 synthetic fixture data cells match ground truth**, with exact headers and exact-row recall. See `reports/benchmark.json` and `reports/ACCURACY_REPORT.md` for methodology and limitations.
- **50-page stress test:** one joined table, 501 rows, 12 columns, all source cells preserved, 49 repeated headers removed.
- **Borderless regression:** two-page digital fixture preserves multiword headers and all data cells, with alignment marked for review.
- **Browser flow:** real invoice, scan and bank fixture extraction; row-to-source highlight on page 2; validation-to-row navigation; missing-currency correction; finding count changes from 6 to 5; one correction remains in history; Excel downloaded successfully.
- **Export inspection:** five sheet types, typed numbers/dates/percentages, preserved identifiers, filtered/frozen table data, matching evidence row counts and string-only untrusted formula-like content.
- **CLI:** bank statement exported to Excel and JSON, with 21 rows and six source findings.
- **Visual inspection:** rendered sample PDFs inspected for legibility and table alignment. Desktop and mobile browser screenshots are in `docs/screenshots/`.
- **Video:** H.264 MP4, 1920 × 1080, 12 frames/second, exactly 150 seconds. Captioned walkthrough using real UI captures, not an uncut performance recording.
- **Static checks:** Python compilation and JavaScript syntax checks pass. Python and frontend sources are formatted for readability.

Linux and Docker configurations are supplied; remote CI results, when available, are visible under the repository's Actions tab. This record does not claim those environments were manually verified locally.
