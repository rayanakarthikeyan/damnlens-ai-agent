# LedgerLens demonstration

The supplied video is a captioned walkthrough assembled from actual application screenshots. It is not an uncut real-time performance recording. Processing timings in the video are those displayed by the application; screenshot display durations are editorial. A live demonstration is recommended when presenting to the judges.

Target length: 2 minutes 30 seconds. All data is fictional. The video includes the actual workspace, extraction results, source evidence, validation, editing, OCR and measured report.

1. **00:00–00:15 — Workspace.** Introduce LedgerLens: local document intelligence with a usable review process. No API key. Drag-and-drop or use a sample.
2. **00:15–00:30 — Digital extraction.** Three invoice pages become one 12-column table. Thirty-one rows include the original total. Two repeated page headers are removed.
3. **00:30–00:45 — Traceability.** Click an extracted row and compare its highlighted location on the original page. Provenance survives stitching and export.
4. **00:45–01:00 — Agent activity.** Show inspect, extract, stitch and validate. Duplicate business rows are preserved. Empty pages and failed extractions are review findings.
5. **01:00–01:15 — Scanned documents.** Show the image-only inventory result. OCR runs locally using an English PP-OCR model; OpenCV reconstructs the grid.
6. **01:15–01:30 — Validation.** The bank statement includes a wrong total, an altered running balance and missing fields. Show actual warnings and their row references.
7. **01:30–01:45 — Correction.** Open the cell editor. Changes preserve the original value in history and rerun validation. Avoid silently rewriting the source.
8. **01:45–02:00 — Reviewed result.** Show the refreshed findings and correction history. Explain that exported workbooks include typed data, findings, evidence and corrections.
9. **02:00–02:15 — Measured accuracy.** Show all three development fixtures against ground truth: 864 cells. These are synthetic results, not a guarantee for hidden PDFs. A separate 50-page test verifies 501 rows.
10. **02:15–02:30 — Ready to run.** Show the workspace and submission package: open source, reproducible benchmarks, README, three PDF/Excel pairs and this demo. Explain practical limits honestly.
