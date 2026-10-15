# LedgerLens demonstration

The supplied video is a captioned walkthrough assembled from actual application screenshots. It is not an uncut real-time performance recording. Processing timings in the video are those displayed by the application; screenshot display durations are editorial. A live demonstration is recommended when presenting to the judges.

Target length: 2 minutes 30 seconds. All data is fictional. The video includes the actual workspace, extraction results, source evidence, validation, editing, OCR and measured report.

1. **00:00–00:15 — Workspace.** Introduce the operational extraction queue, pending reviews, findings and the visible accuracy workflow. Upload a PDF/scan or run a fixture.
2. **00:15–00:30 — Digital extraction.** Three invoice pages become one 12-column table. Thirty-one rows include the original total. Two repeated page headers are removed.
3. **00:30–00:45 — Traceability.** Click an extracted row and compare its highlighted location on the original page. Provenance survives stitching and export.
4. **00:45–01:00 — Agent activity.** Show timestamped routing, extraction, alignment and validation events. Page coverage and source evidence are distinct from accuracy measurements. Prior retries remain downloadable.
5. **01:00–01:15 — Scanned documents.** Show the image-only inventory result. OCR runs locally using an English PP-OCR model; OpenCV reconstructs the grid.
6. **01:15–01:30 — Validation.** The bank statement includes a wrong total, an altered running balance and missing fields. Show actual warnings and their row references.
7. **01:30–01:45 — Review checkpoint.** Confirm source and alignment checks, acknowledge outstanding findings and enter a note. A correction preserves the old value, reruns validation and revokes the prior review.
8. **01:45–02:00 — Reviewed export.** Show that accepted findings remain visible. Excel records draft/reviewed status, typed data, validation, evidence, corrections, page coverage and the run log.
9. **02:00–02:15 — Measured accuracy.** Show all three development fixtures against ground truth: 864 cells. These are synthetic results, not a guarantee for hidden PDFs. A separate 50-page test verifies 501 rows.
10. **02:15–02:30 — Ready to run.** Show the workspace and submission package: open source, reproducible benchmarks, README, three PDF/Excel pairs and this demo. Explain practical limits honestly.
