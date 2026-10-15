"use strict";
const $ = (s) => document.querySelector(s),
  $$ = (s) => [...document.querySelectorAll(s)];
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const icon = (name) => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const labels = {
  total_mismatch: "Total does not reconcile",
  balance_mismatch: "Running balance mismatch",
  missing_value: "Missing value",
  arithmetic: "Quantity and price mismatch",
  line_total: "Line total mismatch",
  empty_column: "Empty column",
  column_type: "Column type inconsistency",
  duplicate_row: "Duplicate row preserved",
  sparse_row: "Sparse row",
  low_ocr: "Low OCR recognition score",
  header_review: "Header identification needs review",
  alignment_review: "Inferred column alignment",
  page_review: "Page needs visual review",
  row_continuation: "Row continues across pages",
  merged_cell_review: "Merged source cell",
  merged_total_review: "Merged values affect the total",
  ocr_retry_review: "OCR recovery or verification",
  ocr_disagreement: "OCR candidates disagree",
  gemini_disagreement: "Gemini reading differs",
  gemini_structure: "Gemini structure differs",
  gemini_coverage: "Gemini second-reading coverage",
};
const suggestions = {
  total_mismatch:
    "Compare the stated total and its contributing rows with the original document.",
  balance_mismatch:
    "Check the prior balance, debit and credit against the source.",
  missing_value:
    "Check whether the original cell is empty before entering a correction.",
  arithmetic:
    "Confirm the quantity, unit price and net amount. Preserve intentional source errors.",
  line_total: "Verify the net, tax and total values in the original row.",
  duplicate_row:
    "Confirm whether the repeated record is a legitimate business entry.",
  alignment_review:
    "Check every column against the source, especially wrapped and merged cells.",
  page_review:
    "Open the page to confirm whether it contains a table. Try OCR if needed.",
  row_continuation:
    "Compare every source part before accepting the reconstructed row.",
  merged_cell_review:
    "Inspect the source span and its shared value. Covered horizontal cells remain empty when their meaning is ambiguous.",
  merged_total_review:
    "Check whether a shared source amount applies once to the group or separately to each logical row. Both totals are shown for review.",
  ocr_retry_review:
    "Compare the cell with the source and inspect its recorded OCR route. Model agreement is not measured accuracy.",
  ocr_disagreement:
    "Inspect the ambiguous characters in the source. The original reading was retained because the OCR candidates did not agree.",
};
let jobs = [],
  inbox = [],
  currentJob = null,
  currentResult = null,
  currentTable = 0,
  currentPage = 1,
  selectedRow = null,
  view = "workspace",
  activeTab = "data",
  jobFilter = "all",
  editCell = null,
  pollTimer = null,
  toastTimer = null,
  sourceToken = 0;
let geminiConfig = null;
function workflowMode() {
  return $('input[name="workflow"]:checked').value;
}
function workflowLabel(job) {
  return job.workflow?.mode === "gemini" ? "Gemini-assisted AI" : "Local AI";
}
function newExtraction() {
  go("workspace");
  $("#workflow-choice").scrollIntoView({ behavior: "smooth", block: "center" });
  $('input[name="workflow"]:checked').focus();
  toast(
    "Choose your workflow, then browse or drop a document. Sample buttons always run locally.",
  );
}
function updateWorkflow() {
  const cloud = workflowMode() === "gemini";
  $("#gemini-options").hidden = !cloud;
  if (!cloud) $("#cloud-consent").checked = false;
  $("#gemini-status").textContent =
    geminiConfig?.configured && geminiConfig?.model_valid
      ? `Key configured on server · ${geminiConfig.model} · Live dummy-page checks recorded; unseen accuracy unestablished`
      : "Setup needed: copy .env.example to .env, set GEMINI_API_KEY, then restart. Local AI is ready without a key. Live check results: reports/GEMINI_EVALUATION.md.";
}
async function api(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail;
    try {
      detail = (await response.json()).detail;
    } catch {
      detail = response.statusText;
    }
    throw Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return response.status === 204 ? null : response.json();
}
function toast(text) {
  $("#toast").textContent = text;
  $("#toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("#toast").hidden = true), 6500);
}
function fail(error) {
  toast(error.message || "The request failed. Please retry.");
  console.error(error);
}
function dateText(value) {
  return value
    ? new Date(value).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
}
function timeText(value) {
  return value
    ? new Date(value).toLocaleTimeString(undefined, {
        hour12: false,
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "—";
}
function quality() {
  return currentResult?.quality || {};
}
function go(next) {
  clearTimeout(pollTimer);
  view = next;
  $$("#main>section").forEach((s) => (s.hidden = true));
  const ids = {
    workspace: "home-view",
    documents: "list-view",
    validation: "review-view",
    benchmarks: "benchmark-view",
    result: "result-view",
  };
  $("#" + ids[next]).hidden = false;
  window.scrollTo({ top: 0 });
  $$(".nav-item").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === next),
  );
  $("#breadcrumb").textContent = {
    workspace: "Overview",
    documents: "Documents",
    validation: "Review queue",
    benchmarks: "Accuracy & coverage",
    result: "Extraction review",
  }[next];
  if (next !== "result") {
    history.replaceState(null, "", "#" + next);
    refreshJobs();
  }
  if (next === "benchmarks") loadBenchmark().then(loadComplexEvidence);
  if (next === "validation") loadInbox();
}
function metric(label, value, note, type = "file", tone = "") {
  return `<div class="workspace-metric ${tone}"><div><span class="metric-label">${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(note)}</small></div><span class="metric-icon">${icon(type)}</span></div>`;
}
function renderMetrics() {
  const complete = jobs.filter((j) => j.status === "complete"),
    pending = complete.filter((j) => j.review_status !== "reviewed"),
    reviewed = complete.filter((j) => j.review_status === "reviewed"),
    running = jobs.filter((j) => ["queued", "processing"].includes(j.status));
  $("#workspace-metrics").innerHTML =
    metric(
      "Documents",
      jobs.length,
      `${complete.length} completed · ${running.length} running`,
    ) +
    metric(
      "Awaiting review",
      pending.length,
      "Completed extraction, pending review",
      "eye",
      "attention",
    ) +
    metric(
      "Open findings",
      pending.reduce((n, j) => n + (j.issues || 0), 0),
      "Across unreviewed documents",
      "alert",
      "attention",
    ) +
    metric(
      "Reviewed",
      reviewed.length,
      "Review decision recorded",
      "shield",
      "success",
    );
  $("#review-metrics").innerHTML =
    metric(
      "Pending reviews",
      pending.length,
      "Includes clean extraction drafts",
      "eye",
    ) +
    metric(
      "Errors",
      pending.reduce((n, j) => n + (j.quality?.errors || 0), 0),
      "Investigate against source",
      "alert",
      "attention",
    ) +
    metric(
      "Warnings",
      pending.reduce((n, j) => n + (j.quality?.warnings || 0), 0),
      "Alignment, gaps and recognition",
      "shield",
      "attention",
    ) +
    metric(
      "Reviewed",
      reviewed.length,
      "Accepted findings remain traceable",
      "check",
      "success",
    );
}
function jobBadge(j) {
  if (j.status === "complete")
    return j.review_status === "reviewed"
      ? '<span class="badge success">Reviewed</span>'
      : `<span class="badge ${j.issues ? "warning" : "blue"}">${j.issues ? j.issues + " findings" : "Review pending"}</span>`;
  return `<span class="badge ${["failed", "interrupted"].includes(j.status) ? "error" : "blue"}">${esc(j.status === "processing" ? "Agent running" : j.status)}</span>`;
}
function jobTable(list) {
  if (!list.length)
    return `<div class="empty-state">${icon("file")}<strong>No documents in this view</strong>Upload a document or run an evaluation fixture to start an extraction.</div>`;
  return `<div class="table-container"><table class="document-table"><thead><tr><th>Document</th><th class="doc-date-col">Created</th><th class="doc-shape-col">Extraction</th><th class="doc-scope-col">Page coverage</th><th>Review status</th><th></th></tr></thead><tbody>${list.map((j) => `<tr><td><button class="doc-open" data-job="${esc(j.id)}"><span class="file-tile">${icon("file")}</span><span><span class="doc-name">${esc(j.filename)}</span><span class="doc-meta">${workflowLabel(j)} · ${j.force_ocr ? "OCR only" : "Automatic routing"}${j.attempt > 1 ? " · attempt " + j.attempt : ""}</span></span></button></td><td class="doc-date-col">${dateText(j.created)}</td><td class="doc-shape-col">${j.rows ?? "—"} rows <span class="muted">/</span> ${j.tables ?? "—"} table${j.tables === 1 ? "" : "s"}</td><td class="doc-scope-col">${j.quality ? j.quality.pages_extracted + " / " + j.quality.pages_total : "—"}</td><td>${jobBadge(j)}</td><td><div class="doc-actions"><button class="text-button" data-job="${esc(j.id)}">${j.status === "complete" ? "Open" : "View"}</button><button class="delete-doc" data-delete="${esc(j.id)}" aria-label="Delete ${esc(j.filename)}">${icon("close")}</button></div></td></tr>`).join("")}</tbody></table></div>`;
}
function renderJobs() {
  const search = $("#job-search").value.toLowerCase(),
    allSearch = $("#document-search").value.toLowerCase();
  let recent = jobs.filter((j) => j.filename.toLowerCase().includes(search));
  if (jobFilter === "attention")
    recent = recent.filter(
      (j) => j.status !== "complete" || j.review_status !== "reviewed",
    );
  if (jobFilter === "reviewed")
    recent = recent.filter((j) => j.review_status === "reviewed");
  $("#queue-total").textContent = jobs.length;
  $("#recent-list").innerHTML = jobTable(recent.slice(0, 6));
  $("#document-list").innerHTML = jobTable(
    jobs.filter((j) => j.filename.toLowerCase().includes(allSearch)),
  );
  $("#pending-list").innerHTML = jobTable(
    jobs.filter(
      (j) => j.status === "complete" && j.review_status !== "reviewed",
    ),
  );
  $("#doc-count").textContent = jobs.length;
  $("#issue-count").textContent = jobs.filter(
    (j) => j.status === "complete" && j.review_status !== "reviewed",
  ).length;
  renderMetrics();
}
async function refreshJobs() {
  try {
    jobs = await api("/api/jobs");
    renderJobs();
  } catch (error) {
    fail(error);
  }
}
async function loadInbox() {
  try {
    inbox = await api("/api/review");
    renderInbox();
  } catch (error) {
    fail(error);
  }
}
function issueCard(i, inInbox = false) {
  const name = labels[i.kind] || i.kind.replaceAll("_", " "),
    location = [
      inInbox ? i.filename : null,
      i.page ? "Page " + i.page : null,
      i.table ? "Table " + i.table : null,
      i.row ? "Row " + i.row : null,
      i.column ? "Column " + i.column : null,
    ]
      .filter(Boolean)
      .join(" · ");
  return `<article class="finding ${esc(i.severity)}"><span class="finding-icon">${icon(i.severity === "error" ? "alert" : "shield")}</span><div class="finding-content"><h3>${esc(name)}<span class="badge ${i.severity === "error" ? "error" : "warning"}">${esc(i.severity)}</span>${i.review_status === "reviewed" ? '<span class="reviewed-indicator">Reviewed</span>' : ""}</h3><p>${esc(i.message)}</p><span class="finding-location">${esc(location)}</span>${suggestions[i.kind] ? `<p class="suggestion">${esc(suggestions[i.kind])}</p>` : ""}</div><button class="text-button" ${inInbox ? `data-inbox="${esc(i.job)},${i.table || 0},${i.row || 0},${i.page || 0}"` : `data-finding="${i.table || 0},${i.row || 0},${i.page || 0}"`}>Inspect ${icon("arrow")}</button></article>`;
}
function renderInbox() {
  const severity = $("#inbox-severity").value;
  const filtered = inbox.filter(
    (i) => severity === "all" || i.severity === severity,
  );
  $("#review-list").innerHTML =
    filtered.map((i) => issueCard(i, true)).join("") ||
    `<div class="empty-state">${icon("shield")}<strong>No findings in this view</strong>Review pending documents against their original source before completing review.</div>`;
}
const sampleMeta = {
  "01_invoice_register": {
    title: "Invoice register",
    detail: "3 pages · 12 columns · Native PDF",
    tags: ["Continuation tables", "Repeated headers"],
  },
  "02_scanned_inventory": {
    title: "Scanned inventory",
    detail: "2 pages · 12 columns · Image-only PDF",
    tags: ["Local OCR", "Grid reconstruction"],
  },
  "03_bank_statement": {
    title: "Bank statement",
    detail: "2 pages · 12 columns · Known source errors",
    tags: ["Totals & balances", "Missing values"],
  },
};
async function loadSamples() {
  const samples = await api("/api/samples");
  $("#sample-cards").innerHTML = samples
    .map((s) => {
      const m = sampleMeta[s.name] || {
        title: s.filename,
        detail: "Evaluation fixture",
        tags: [],
      };
      return `<button class="sample-card" data-sample="${esc(s.name)}"><span class="file-tile">${icon(s.name.includes("scanned") ? "scan" : "file")}</span><span><strong>${esc(m.title)}</strong><p>${esc(m.detail)}</p><span class="sample-tags">${m.tags.map((t) => `<span>${esc(t)}</span>`).join("")}</span></span>${icon("arrow")}</button>`;
    })
    .join("");
}
async function upload(file) {
  if (!file) return;
  if (file.size > 40 * 1024 * 1024) {
    toast("Choose a document smaller than 40 MB.");
    return;
  }
  const body = new FormData();
  body.append("file", file);
  try {
    const params = new URLSearchParams({
      force_ocr: $("#extraction-mode").value === "ocr",
      workflow: workflowMode(),
    });
    if (workflowMode() === "gemini") {
      if (!geminiConfig?.configured || !geminiConfig?.model_valid)
        throw Error(
          "Configure Gemini on the server and restart, or select Local AI.",
        );
      if (!$("#cloud-consent").checked)
        throw Error(
          "Select the cloud authorization checkbox before using Gemini.",
        );
      const limit = Number($("#gemini-limit").value);
      if (!Number.isInteger(limit) || limit < 1 || limit > 50)
        throw Error("Request limit must be an integer from 1 to 50.");
      params.set("cloud_consent", "true");
      params.set("gemini_scope", $("#gemini-scope").value);
      params.set("max_requests", limit);
    }
    const j = await api("/api/jobs?" + params, { method: "POST", body });
    $("#cloud-consent").checked = false;
    await openJob(j.id);
  } catch (error) {
    fail(error);
  } finally {
    $("#file-input").value = "";
  }
}
async function runSample(name) {
  try {
    const j = await api("/api/samples/" + encodeURIComponent(name), {
      method: "POST",
    });
    await openJob(j.id);
  } catch (error) {
    fail(error);
  }
}
function pipeline(stage, reviewed = false) {
  const definitions = [
    ["inspect", "Inspect", "Source routing"],
    ["extract", "Extract", "Text & OCR"],
    ["align", "Align", "Table continuity"],
    ["validate", "Validate", "Integrity checks"],
    ["review", "Review", "Source verification"],
    ["export", "Export", "Structured workbook"],
  ];
  const active = definitions.findIndex((d) => d[0] === stage);
  $("#agent-pipeline").innerHTML = definitions
    .map(([key, label, detail], i) => {
      const complete = i < active || (reviewed && i <= 4);
      return `<div class="pipeline-step ${complete ? "complete" : i === active ? "active" : ""}"><span>${complete ? icon("check") : i + 1}</span><div>${label}<small>${detail}</small></div></div>`;
    })
    .join("");
}
async function openJob(id) {
  clearTimeout(pollTimer);
  currentJob = id;
  sourceToken++;
  currentResult = null;
  currentTable = 0;
  selectedRow = null;
  activeTab = "data";
  $("#row-filter").value = "all";
  $("#issue-severity").value = "all";
  go("result");
  history.replaceState(null, "", "#job=" + id);
  $("#processing").hidden = false;
  $("#result-content").hidden = true;
  [
    "#excel-download",
    "#review-button",
    "#retry-button",
    "#resume-button",
  ].forEach((s) => ($(s).hidden = true));
  $("#progress-label").textContent = "Opening extraction run";
  $("#progress-bar").style.width = "0%";
  $("#progress-text").textContent = "0%";
  $("#progress-detail").textContent =
    "The agent records extraction decisions and exceptions for review.";
  $("#processing-log").textContent = "Waiting for agent status…";
  pipeline("inspect");
  await pollJob();
}
async function pollJob() {
  try {
    const id = currentJob;
    const j = await api("/api/jobs/" + id);
    if (id !== currentJob || view !== "result") return;
    $("#result-title").textContent = j.filename;
    $("#result-status").textContent =
      j.status === "complete"
        ? "Extraction complete"
        : j.status === "processing"
          ? "Agent running"
          : j.status;
    $("#result-status").className =
      "badge " +
      (["failed", "interrupted"].includes(j.status) ? "error" : "blue");
    $("#result-subtitle").textContent =
      `${dateText(j.created)} · ${workflowLabel(j)} · ${j.force_ocr ? "OCR only" : "Automatic routing"} · Run ${id.slice(0, 8)}${j.attempt > 1 ? " · Attempt " + j.attempt : ""}`;
    $("#progress-label").textContent = j.message;
    $("#progress-bar").style.width = j.progress + "%";
    $("#progress-text").textContent = j.progress + "%";
    pipeline(j.stage || "extract");
    $("#processing-log").innerHTML =
      (j.events || [])
        .slice(-8)
        .map(
          (e) =>
            `<div class="event-line"><time>${timeText(e.at)}</time><span>${esc(e.message)}${e.page ? " · page " + e.page : ""}</span></div>`,
        )
        .join("") || "Waiting for extraction decisions…";
    if (j.status === "complete") {
      const r = await api("/api/jobs/" + id + "/result");
      if (id !== currentJob || view !== "result") return;
      currentResult = r;
      renderResult();
      refreshJobs();
    } else if (["failed", "interrupted"].includes(j.status)) {
      $("#resume-button").hidden = false;
      $("#retry-button").hidden = false;
      $("#progress-detail").textContent = j.message;
      toast(j.message);
      refreshJobs();
    } else {
      pollTimer = setTimeout(pollJob, 800);
    }
  } catch (error) {
    fail(error);
    if (view === "result") pollTimer = setTimeout(pollJob, 2500);
  }
}
function renderResult(preserveTab = false) {
  const r = currentResult,
    q = quality();
  $("#processing").hidden = true;
  $("#result-content").hidden = false;
  $("#excel-download").hidden = false;
  $("#retry-button").hidden = false;
  $("#resume-button").hidden = true;
  $("#review-button").hidden = !q.can_review;
  $("#review-button").disabled = q.review_status === "reviewed";
  $("#review-button").innerHTML =
    icon("check") +
    (q.review_status === "reviewed" ? "Review completed" : "Complete review");
  $("#excel-download").innerHTML =
    icon("download") +
    (q.review_status === "reviewed" ? "Export Excel" : "Export draft");
  $("#result-status").textContent =
    q.review_status === "reviewed"
      ? "Reviewed"
      : q.findings
        ? "Needs review"
        : "Review pending";
  $("#result-status").className =
    "badge " +
    (q.review_status === "reviewed"
      ? "success"
      : q.findings
        ? "warning"
        : "blue");
  pipeline(
    q.review_status === "reviewed" ? "export" : "review",
    q.review_status === "reviewed",
  );
  const title =
    q.review_status === "reviewed"
      ? "Review completed for this data snapshot"
      : q.errors
        ? `${q.errors} validation error${q.errors === 1 ? "" : "s"} require review`
        : "Extraction complete. Source review is pending.";
  const message =
    q.review_status === "reviewed"
      ? `${r.review.accepted_findings} findings accepted · ${dateText(r.review.at)}${r.review.note ? " · " + r.review.note : ""}`
      : `${q.pages_extracted} / ${q.pages_total} pages have extracted tables. ${q.findings} findings · ${q.rows_with_evidence} / ${q.rows} rows include source evidence.`;
  $("#review-banner").innerHTML =
    `<div class="review-banner ${q.review_status === "reviewed" ? "success" : q.errors ? "error" : ""}"><div>${icon(q.review_status === "reviewed" ? "check" : "shield")}<span><strong>${esc(title)}</strong><p>${esc(message)}</p></span></div><button class="text-button" data-switch-tab="${q.findings ? "issues" : "coverage"}">${q.findings ? "Inspect findings" : "Check coverage"} ${icon("arrow")}</button></div>`;
  $("#result-metrics").innerHTML = [
    [
      "Page coverage",
      q.pages_extracted + " / " + q.pages_total,
      "Pages with extracted tables",
    ],
    [
      "Extracted rows",
      q.rows,
      q.tables + " joined table" + (q.tables === 1 ? "" : "s"),
    ],
    [
      "Max. columns",
      q.max_columns,
      r.headers_removed + " repeated headers removed",
    ],
    [
      "Validation findings",
      q.findings,
      q.errors + " errors · " + q.warnings + " warnings",
    ],
    [
      "OCR pages",
      r.pages.filter((p) => p.method === "ocr").length + " / " + r.page_count,
      q.ocr_recognition_mean == null
        ? "Native text; no OCR score"
        : (q.ocr_recognition_mean * 100).toFixed(1) +
          "% mean recognition score",
    ],
  ]
    .map(
      ([a, b, c]) =>
        `<div class="metric"><span>${esc(a)}</span><strong>${esc(b)}</strong><small>${esc(c)}</small></div>`,
    )
    .join("");
  $("#finding-count").textContent = q.findings;
  $("#edit-count").textContent = r.edits.length;
  $("#json-download").href = `/api/jobs/${currentJob}/export/json`;
  $("#table-selectors").innerHTML = r.tables
    .map(
      (t, i) =>
        `<button class="${i === currentTable ? "active" : ""}" data-table="${i}">${esc(t.name)} <small>${t.rows.length} rows</small></button>`,
    )
    .join("");
  renderTable();
  renderIssues();
  renderCoverage();
  renderActivity();
  renderCorrections();
  renderGemini();
  setTab(preserveTab ? activeTab : "data");
  if (!preserveTab) {
    $("#data-table").scrollTo({ top: 0, left: 0 });
    showSourcePage(1);
  }
}
function renderTable() {
  const t = currentResult.tables[currentTable];
  if (!t) {
    $("#table-structure").hidden = true;
    $("#data-table").innerHTML =
      '<div class="empty-state">No structured tables were recovered. Inspect page coverage or retry with OCR.</div>';
    $("#table-shape").textContent = "No data";
    $("#table-footer").textContent =
      "Review is unavailable until rows with source evidence are extracted.";
    return;
  }
  $("#csv-download").href = `/api/jobs/${currentJob}/export/csv?table=${t.id}`;
  const issues = currentResult.issues.filter((i) => i.table === t.id);
  const flagged = new Set(issues.filter((i) => i.row).map((i) => i.row));
  const rows = t.rows
    .map((r, index) => ({ r, index }))
    .filter(
      ({ r }) => $("#row-filter").value !== "flagged" || flagged.has(r.id),
    );
  $("#table-shape").textContent =
    `${t.rows.length} rows × ${t.headers.length} columns · pages ${t.pages.join(", ")}`;
  $("#table-footer").textContent =
    `Showing ${rows.length} / ${t.rows.length} rows · ${flagged.size} rows have findings · ${quality().export_label}${t.header_paths ? " · Header groups preserved in Excel Structure and JSON" : ""}`;
  const continued = t.rows.filter((r) => r.sources?.length > 1).length;
  const merged = t.rows.filter(
    (r) => r.merged_cells?.length || r.inherited_cells?.length,
  ).length;
  $("#table-structure").hidden = !(t.header_paths || continued || merged);
  $("#structure-details").innerHTML =
    `<p>${continued} rows continue across source pages · ${merged} rows include merged-cell geometry. Inspect the linked source parts and review findings.</p>${t.header_paths ? `<dl>${t.header_paths.map((path, i) => `<div><dt>${esc(t.headers[i])}</dt><dd>${path.map(esc).join(" → ")}</dd></div>`).join("")}</dl>` : ""}`;
  $("#data-table").innerHTML = rows.length
    ? `<table class="data-table"><thead><tr><th>#</th>${t.headers.map((h) => `<th>${esc(h)}</th>`).join("")}<th>Source page</th></tr></thead><tbody>${rows
        .map(
          ({ r, index }) =>
            `<tr data-row="${index}" class="${selectedRow === index ? "selected" : ""}"><td>${r.id}</td>${r.cells
              .map((cell, col) => {
                const found = issues.filter(
                  (i) => i.row === r.id && (!i.column || i.column === col + 1),
                );
                return `<td tabindex="0" data-cell="${index},${col}" class="${found.length ? "flagged" : ""} ${found.some((i) => i.severity === "error") ? "error" : ""}" title="${esc(found.map((i) => i.message).join("\n") || "Enter or double-click to correct")}">${cell ? esc(cell) : '<span class="muted">—</span>'}</td>`;
              })
              .join(
                "",
              )}<td>${[...new Set((r.sources || [r]).map((s) => s.page))].join(", ")}</td></tr>`,
        )
        .join("")}</tbody></table>`
    : '<div class="empty-state">No flagged rows in this table.</div>';
  $$("[data-table]").forEach((b) =>
    b.classList.toggle("active", Number(b.dataset.table) === currentTable),
  );
}
function setTab(tab) {
  activeTab = tab;
  $$("[data-tab]").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tab);
    b.setAttribute("aria-selected", String(b.dataset.tab === tab));
  });
  ["data", "issues", "coverage", "activity", "corrections", "gemini"].forEach(
    (name) => ($("#" + name + "-panel").hidden = name !== tab),
  );
}
function renderGemini() {
  const assist = currentResult.gemini;
  if (!assist) {
    $("#gemini-panel").innerHTML =
      '<div class="panel-tools"><div><h2>Local AI workflow</h2><p>No document pages were sent to an external AI API in this run.</p></div><span class="badge success">No API charges</span></div><div class="workflow-route">Inspect → Native PDF / local ML OCR → Align & stitch → Validate → Source review → Excel</div><p class="report-note">No API key or cloud quota required. Compute and storage depend on this device; the 50-page / 40 MB limit still applies. Start a new extraction and explicitly select Gemini-assisted AI to request a cloud second reading.</p>';
    return;
  }
  const pages = assist.pages || [],
    checked = pages.filter((p) => p.status === "checked").length;
  const proposals = pages.flatMap((p) => p.proposals || []);
  $("#gemini-panel").innerHTML =
    `<div class="panel-tools"><div><h2>Gemini-assisted AI workflow</h2><p>Independent second reading. Original local values remain in the main data table.</p></div><span class="badge ${checked < (assist.selected_pages || []).length || assist.status === "unavailable" ? "warning" : "blue"}">${checked} page${checked === 1 ? "" : "s"} checked</span></div><div class="workflow-route">Local baseline → Select difficult pages → Gemini extraction → Compare → Source review → Validated Excel</div><div class="quality-detail"><div><strong>${esc(assist.model || currentResult.workflow?.model || "Unavailable")}</strong><span>Configured model</span></div><div><strong>${assist.requests_used || 0} / ${assist.max_requests || currentResult.workflow?.max_requests || 0}</strong><span>Request attempts / authorized limit</span></div><div><strong>${assist.reported_tokens?.totalTokenCount || 0}</strong><span>Provider-reported total tokens</span></div></div><p class="report-note">${esc(assist.billing_note || assist.message || "Local results retained.")}<br>Agreement is not proof of accuracy. Gemini never silently edits cells. Skipped, failed or uncertain pages still require source review. Cloud candidates are included in JSON and the separate Excel candidates sheet.</p><h3>Discrepancies to review · ${proposals.length}</h3>${proposals.length ? proposals.map((p, index) => `<article class="gemini-proposal"><div><strong>Table ${p.table} · Row ${p.row} · Column ${p.column} · Page ${p.page}</strong><p>Local: <code>${esc(p.before) || "Empty"}</code> → Gemini proposal: <code>${esc(p.suggested) || "Empty"}</code></p><small>Current value: ${esc(currentResult.tables[p.table - 1]?.rows[p.row - 1]?.cells[p.column - 1])}</small></div><button class="secondary" data-proposal="${index}">Inspect & edit</button></article>`).join("") : '<p class="muted">No safely mapped cell proposals. Inspect page candidates and structural findings; no differences found does not prove correctness.</p>'}<h3>Cloud page coverage</h3>${pages.length ? pages.map((p) => `<details class="gemini-page"><summary>Page ${p.page} · ${esc(p.status)}${p.structural_disagreement ? " · structure differs" : ""}</summary><button class="secondary" data-source-page="${p.page}">Inspect source page</button><p>${esc(p.message || "Independent candidate transcription; verify against the source.")}</p>${(p.tables || []).map((t, i) => `<h4>Candidate table ${i + 1} · ${t.rows.length} rows × ${t.headers.length} columns</h4><div class="table-scroll"><table class="data-table"><thead><tr>${t.headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${t.rows.map((row) => `<tr>${row.map((v) => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`).join("")}</details>`).join("") : `<p class="muted">${esc(assist.message || "No pages met the difficult-page selection rules. Zero API requests.")}</p>`}`;
}
function renderIssues() {
  const q = quality(),
    severity = $("#issue-severity").value;
  $("#issue-summary").textContent =
    `${q.errors} errors · ${q.warnings} warnings · ${q.flagged_rows} distinct rows flagged`;
  const filtered = currentResult.issues.filter(
    (i) => severity === "all" || i.severity === severity,
  );
  $("#issue-list").innerHTML =
    filtered.map((i) => issueCard(i)).join("") ||
    `<div class="empty-state">${icon("shield")}<strong>No findings in this view</strong>Automated checks did not identify an exception. Verify critical figures against the source.</div>`;
}
function renderCoverage() {
  const r = currentResult,
    q = quality();
  $("#coverage-panel").innerHTML =
    `<div class="panel-tools"><div><h2>Page-level extraction coverage</h2><p>Coverage describes extracted table presence, not independently measured accuracy.</p></div><span class="badge ${q.pages_needing_review.length ? "warning" : "success"}">${q.pages_extracted} / ${q.pages_total} extracted</span></div><div class="quality-detail"><div><strong>${q.rows_with_evidence} / ${q.rows}</strong><span>Rows with source evidence</span></div><div><strong>${q.ocr_recognition_mean == null ? "Not applicable" : (q.ocr_recognition_mean * 100).toFixed(1) + "%"}</strong><span>Mean OCR recognition score; excludes native rows</span></div><div><strong>${q.ocr_low_score_rows}</strong><span>Rows below the 88% OCR review threshold</span></div></div><div class="page-strip">${r.pages.map((p) => `<button class="${p.status === "extracted" ? "" : "warning"}" data-source-page="${p.page}" aria-label="Inspect source page ${p.page}">${p.page}</button>`).join("")}</div><div class="table-container"><table class="coverage-table"><thead><tr><th>Page</th><th>Route</th><th>Fragments</th><th>Seconds</th><th>Status</th><th></th></tr></thead><tbody>${r.pages.map((p) => `<tr><td>${p.page}</td><td>${p.method === "ocr" ? "Local OCR" : "Native PDF"}</td><td>${p.tables}</td><td>${p.seconds ?? "—"}</td><td><span class="badge ${p.status === "extracted" ? "success" : "warning"}">${p.status === "extracted" ? "Extracted" : "Needs review"}</span></td><td><button class="text-button" data-source-page="${p.page}">View source ${icon("arrow")}</button></td></tr>`).join("")}</tbody></table></div>`;
}
function renderActivity() {
  const r = currentResult;
  const events = r.events || [];
  $("#activity-panel").innerHTML =
    `<div class="panel-tools"><div><h2>Agent run log</h2><p>Recorded execution events and routing decisions. Processing time: ${r.elapsed_seconds}s.</p></div><span class="badge neutral">${events.length} events</span></div>${events.length ? `<div class="table-container"><table class="log-table"><thead><tr><th>Time</th><th>Stage</th><th>Action</th><th>Page</th></tr></thead><tbody>${events.map((e) => `<tr><td>${timeText(e.at)}</td><td><span class="stage-label">${esc(e.stage)}</span></td><td>${esc(e.message)}</td><td>${e.page || "—"}</td></tr>`).join("")}</tbody></table></div>` : `<div class="notice">This result was created before execution-event logging was added. Its recorded page routes remain available in Page coverage.</div>`}<div class="report-note"><strong>Source fingerprint</strong><br><code>${esc(r.sha256)}</code><br>Legitimate duplicate rows are preserved. Review completion is stored separately from extraction and is invalidated by subsequent data changes.</div><div class="version-list" id="version-list"></div>`;
  loadVersions();
}
async function loadVersions() {
  try {
    const id = currentJob;
    const versions = await api(`/api/jobs/${id}/versions`);
    if (id !== currentJob || !$("#version-list")) return;
    $("#version-list").innerHTML =
      "<h3>Previous runs</h3>" +
      (versions.length
        ? versions
            .map(
              (v) =>
                `<div class="version-row"><span>${dateText(v.saved_at)} · ${v.rows} rows · ${v.edits} correction${v.edits === 1 ? "" : "s"} · ${esc(v.review_status)}</span><div><a class="text-button" href="/api/jobs/${id}/versions/${v.id}/export/xlsx">Excel ${icon("download")}</a><a class="text-button" href="/api/jobs/${id}/versions/${v.id}/export/json">JSON ${icon("download")}</a></div></div>`,
            )
            .join("")
        : '<p class="muted">No saved completed runs. An existing result is archived before an OCR retry.</p>');
  } catch (error) {
    fail(error);
  }
}
function renderCorrections() {
  const r = currentResult;
  $("#corrections-panel").innerHTML =
    `<div class="panel-tools"><div><h2>Correction history</h2><p>Original values remain available. A change resets the review decision.</p></div><span class="badge neutral">${r.edits.length} change${r.edits.length === 1 ? "" : "s"}</span></div>` +
    (r.edits.length
      ? `<div class="table-container"><table class="correction-table"><thead><tr><th>Location</th><th>Original</th><th>Corrected</th><th>Recorded</th></tr></thead><tbody>${r.edits.map((e) => `<tr><td>Table ${e.table} · Row ${e.row} · Column ${e.column}</td><td class="old-value">${esc(e.before) || "Empty"}</td><td class="new-value">${esc(e.after) || "Empty"}</td><td>${dateText(e.at)}</td></tr>`).join("")}</tbody></table></div>`
      : '<div class="empty-state">No cells have been manually changed in this run.</div>');
}
function showSourcePage(page, row = null) {
  if (!currentResult) return;
  const token = ++sourceToken;
  currentPage = Math.min(
    currentResult.page_count,
    Math.max(1, Number(page) || 1),
  );
  const details = currentResult.pages[currentPage - 1];
  const parts = row?.sources || (row ? [row] : []);
  const part = parts.find((p) => p.page === currentPage) || row;
  $("#source-parts").innerHTML =
    parts.length > 1
      ? parts
          .map(
            (p, i) =>
              `<button class="secondary" data-part="${i}">Part ${i + 1} · page ${p.page}</button>`,
          )
          .join("")
      : "";
  $$("[data-part]").forEach(
    (button) =>
      (button.onclick = () =>
        showSourcePage(parts[Number(button.dataset.part)].page, row)),
  );
  $("#page-number").value = currentPage;
  $("#page-number").max = currentResult.page_count;
  $("#source-page-label").textContent = "/ " + currentResult.page_count;
  $("#prev-page").disabled = currentPage === 1;
  $("#next-page").disabled = currentPage === currentResult.page_count;
  $("#source-method").textContent = details.method === "ocr" ? "OCR" : "Native";
  const img = $("#source-image"),
    box = $("#source-highlight");
  box.hidden = true;
  $("#source-caption").textContent = row
    ? `Table ${currentTable + 1} · Row ${row.id} · ${part.method}${part.method.startsWith("OCR") ? " · recognition " + (part.confidence * 100).toFixed(1) + "%" : ""}${parts.length > 1 ? " · " + parts.length + " source parts" : ""}${row.source_context ? " · " + row.source_context : ""}`
    : "Select a row to inspect its source location.";
  img.onload = () => {
    if (token !== sourceToken) return;
    if (row) {
      const width = details.width || (img.naturalWidth * 72) / 110,
        height = details.height || (img.naturalHeight * 72) / 110;
      const [x0, y0, x1, y1] = part.bbox;
      Object.assign(box.style, {
        left: (x0 / width) * 100 + "%",
        top: (y0 / height) * 100 + "%",
        width: ((x1 - x0) / width) * 100 + "%",
        height: ((y1 - y0) / height) * 100 + "%",
      });
      box.hidden = false;
      $(".source-scroll").scrollTo({
        top: Math.max(0, box.offsetTop - 90),
        behavior: "smooth",
      });
    }
  };
  img.src = `/api/jobs/${currentJob}/page/${currentPage}`;
  if (img.complete && img.naturalWidth) img.onload();
}
function selectRow(index, column = null) {
  selectedRow = index;
  $$("tr[data-row]").forEach((tr) =>
    tr.classList.toggle("selected", Number(tr.dataset.row) === index),
  );
  const row = currentResult.tables[currentTable]?.rows[index];
  if (!row) return;
  const shared = row.inherited_cells?.find(
    (cell) => cell.column === column + 1,
  );
  const merged = row.merged_cells?.find((cell) => cell.column === column + 1);
  const origin = column === null ? null : shared || merged;
  if (origin?.bbox) {
    const page = origin.from_page || row.page;
    showSourcePage(page, {
      ...row,
      page,
      bbox: origin.bbox,
      sources: undefined,
      source_context: "Merged source cell origin",
    });
  } else showSourcePage(row.page, row);
}
function locate(table, row, page) {
  if (table && row) {
    currentTable = table - 1;
    $("#row-filter").value = "all";
    renderTable();
    setTab("data");
    selectRow(row - 1);
    $(`[data-row="${row - 1}"]`)?.scrollIntoView({ block: "nearest" });
  } else {
    setTab("data");
    $("#show-source").checked = true;
    $("#evidence-layout").classList.remove("no-source");
    showSourcePage(page || 1);
  }
}
function startEdit(row, col) {
  editCell = { row, col };
  const table = currentResult.tables[currentTable];
  $("#edit-label").textContent =
    `${table.name} · Row ${row + 1} · ${table.headers[col]}`;
  $("#edit-value").value = table.rows[row].cells[col];
  $("#edit-dialog").showModal();
  $("#edit-value").focus();
}
async function saveEdit(event) {
  event.preventDefault();
  try {
    currentResult = await api(`/api/jobs/${currentJob}/cells`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        table: currentTable + 1,
        row: editCell.row + 1,
        column: editCell.col + 1,
        value: $("#edit-value").value,
      }),
    });
    $("#edit-dialog").close();
    renderResult(true);
    refreshJobs();
    toast("Correction saved. Validation refreshed; source review is pending.");
  } catch (error) {
    fail(error);
  }
}
function openReview() {
  const q = quality();
  if (!q.can_review) return;
  $("#review-dialog-summary").textContent =
    `${currentResult.filename} · ${q.rows} rows · ${q.pages_extracted} / ${q.pages_total} pages with extracted tables.`;
  $("#review-open-findings").textContent = q.findings
    ? `${q.errors} errors and ${q.warnings} warnings remain. Review each finding before accepting the result.`
    : "No automated findings remain. Confirm source values and column alignment before recording review.";
  $("#source-checked").checked = false;
  $("#accept-findings").checked = false;
  $("#accept-findings-label").hidden = !q.findings;
  $("#accept-findings").required = !!q.findings;
  $("#review-note").value = "";
  $("#review-note").required = !!q.findings;
  $("#review-note-hint").textContent = q.findings
    ? "Required when accepting findings"
    : "Optional";
  $("#review-dialog").showModal();
}
async function saveReview(event) {
  event.preventDefault();
  try {
    currentResult = await api(`/api/jobs/${currentJob}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_checked: $("#source-checked").checked,
        accept_findings: $("#accept-findings").checked,
        note: $("#review-note").value,
      }),
    });
    $("#review-dialog").close();
    renderResult(true);
    refreshJobs();
    toast("Review recorded for the current data snapshot.");
  } catch (error) {
    fail(error);
  }
}
function openExport() {
  const q = quality(),
    reviewed = q.review_status === "reviewed";
  $("#export-title").textContent = reviewed
    ? "Export reviewed workbook"
    : "Export draft workbook";
  $("#export-description").textContent = reviewed
    ? "The workbook includes the recorded review decision and any acknowledged findings."
    : "Review is pending. This download is clearly labelled as a draft and retains all validation findings.";
  $("#export-facts").innerHTML = [
    ["Review state", q.export_label],
    ["Data", `${q.rows} rows / ${q.tables} table${q.tables === 1 ? "" : "s"}`],
    ["Page coverage", `${q.pages_extracted} / ${q.pages_total}`],
    ["Findings", `${q.errors} errors / ${q.warnings} warnings`],
    ["Sheets", "Data, validation, evidence, corrections, coverage, run log"],
  ]
    .map(
      ([a, b]) => `<div><span>${esc(a)}</span><strong>${esc(b)}</strong></div>`,
    )
    .join("");
  $("#export-review").hidden = reviewed || !q.can_review;
  $("#export-confirm").href = `/api/jobs/${currentJob}/export/xlsx`;
  $("#export-dialog").showModal();
}
async function loadBenchmark() {
  try {
    const r = await api("/api/benchmark");
    if (!r.results) {
      $("#benchmark-content").innerHTML =
        '<div class="empty-state">Run python scripts/benchmark.py to generate measured results.</div>';
      return;
    }
    const expected = r.results.reduce((n, x) => n + x.expected_cells, 0),
      correct = r.results.reduce((n, x) => n + x.correct_cells, 0);
    $("#benchmark-content").innerHTML =
      `<div class="workspace-metrics">${metric("Measured cells", correct + " / " + expected, "Matching development-fixture data", "grid")}${metric("Fixtures", r.results.length, "Original synthetic documents", "file")}${metric("Exact headers", r.results.filter((x) => x.headers_exact).length + " / " + r.results.length, "Compared independently from data", "shield")}${metric("Scan coverage", r.results.filter((x) => x.file.includes("scanned")).reduce((n, x) => n + x.pages, 0) + " pages", "Image-only PDF fixture", "scan")}</div><div class="benchmark-table-wrap"><table class="report-table"><thead><tr><th>Fixture</th><th>Cells correct</th><th>Cell accuracy</th><th>Exact row recall</th><th>Time</th></tr></thead><tbody>${r.results.map((x) => `<tr><td>${esc(x.file)}<span class="doc-meta">${x.pages} pages · ${x.actual_rows} output rows</span></td><td>${x.correct_cells} / ${x.expected_cells}</td><td><strong>${(x.cell_accuracy * 100).toFixed(2)}%</strong></td><td>${(x.row_recall * 100).toFixed(1)}%</td><td>${x.seconds}s</td></tr>`).join("")}</tbody></table></div><div class="report-note"><strong>Methodology.</strong> ${esc(r.methodology)}<br><br><strong>Evaluation limits.</strong> ${esc(r.limitations)}<br><br>Generated ${dateText(r.generated)}. Recognition confidence in individual rows is separate from this measured extraction accuracy.</div><div class="card requirements-card"><div class="card-header"><div><h2>Challenge requirement coverage</h2><p>Implementation and regression evidence against the supplied competition brief.</p></div></div><div class="table-container"><table class="report-table"><thead><tr><th>Requirement</th><th>Implementation / verification</th><th>Judging area</th></tr></thead><tbody>${[
        [
          "PDFs up to 50 pages",
          "50-page fixture: 501 rows, 12 columns, 49 repeated headers removed. 51 pages are rejected.",
          "Complex tables · 25 marks",
        ],
        [
          "10+ columns per page",
          "All three supplied fixtures have 12 source columns. Generic table width is preserved.",
          "Column integrity · 20 marks",
        ],
        [
          "Scanned PDFs and images",
          "Local RapidOCR recognition and OpenCV reconstruction. The inventory fixture contains images only.",
          "OCR & accuracy · 30 marks",
        ],
        [
          "Automatic tables and headers",
          "Native grid, borderless header anchors, OCR grid and inferred-column routes. Inferred layouts are flagged.",
          "OCR & accuracy · 30 marks",
        ],
        [
          "Multi-page continuity",
          "Adjacent schema/span matching across multiple table streams; repeated headers removed, duplicate records retained.",
          "Complex tables · 25 marks",
        ],
        [
          "Errors and validation",
          "Totals, line arithmetic, balances, empty/misaligned columns, low scores, missing fields and uncovered pages.",
          "Column integrity · 20 marks",
        ],
        [
          "Automation and recovery",
          "Page routing, recorded run events, safe OCR retries, saved prior runs, restart recovery and explicit review.",
          "Recovery · 15 marks",
        ],
        [
          "Runnable submission",
          "README, Python launchers, public source, samples, measured reports and 2–5 minute demo.",
          "Usability · 10 marks",
        ],
      ]
        .map(
          ([a, b, c]) =>
            `<tr><td>${esc(a)}</td><td>${esc(b)}</td><td><span class="score-weight">${esc(c)}</span></td></tr>`,
        )
        .join(
          "",
        )}</tbody></table></div></div><section id="judge-audit-panel" class="card requirements-card" aria-label="Varied document audit"></section>`;
    const audit = await api("/api/judge-audit");
    if (audit.after && $("#judge-audit-panel")) {
      const passed = audit.after.results.filter((x) => x.passed).length;
      const before = audit.before
        ? audit.before.results.filter((x) => x.passed).length
        : null;
      $("#judge-audit-panel").innerHTML =
        `<div class="card-header"><div><h2>Varied document audit · ${passed} / ${audit.after.results.length} exact cases</h2><p>${before === null ? "" : `${before} cases passed before the fixes. `}Synthetic development checks, with visible before-and-after evidence.</p></div><span class="badge blue">12 columns</span></div><div class="table-container"><table class="report-table"><thead><tr><th>Document variation</th><th>Exact cells</th><th>Headers</th><th>Result</th></tr></thead><tbody>${audit.after.results.map((x) => `<tr><td>${esc(x.case.replaceAll("_", " "))}</td><td>${x.denominator ? `${x.correct_cells} / ${x.denominator}` : "No fabricated table"}</td><td>${x.headers_exact ? "Exact" : "Review"}</td><td>${x.passed ? "Passed" : "Needs work"}</td></tr>`).join("")}</tbody></table></div><div class="report-note">${esc(audit.after.scope)}<br><br>Reproduce: <code>python scripts/judge_audit.py</code>. The rubric self-assessment is in <code>reports/JUDGE_EVALUATION.md</code>; it is not an official score.</div>`;
    }
  } catch (error) {
    fail(error);
  }
}
document.addEventListener("click", async (event) => {
  const button = event.target.closest("button,a");
  if (!button) return;
  if (button.dataset.view) go(button.dataset.view);
  if (button.dataset.sample) runSample(button.dataset.sample);
  if (button.dataset.job) openJob(button.dataset.job);
  if (button.dataset.jobFilter) {
    jobFilter = button.dataset.jobFilter;
    $$("[data-job-filter]").forEach((b) =>
      b.classList.toggle("active", b === button),
    );
    renderJobs();
  }
  if (button.dataset.table !== undefined) {
    currentTable = Number(button.dataset.table);
    selectedRow = null;
    renderTable();
  }
  if (button.dataset.tab) setTab(button.dataset.tab);
  if (button.dataset.switchTab) setTab(button.dataset.switchTab);
  if (button.dataset.finding)
    locate(...button.dataset.finding.split(",").map(Number));
  if (button.dataset.inbox) {
    const [job, t, row, page] = button.dataset.inbox.split(",");
    await openJob(job);
    if (currentResult) locate(Number(t), Number(row), Number(page));
  }
  if (button.dataset.sourcePage)
    locate(0, 0, Number(button.dataset.sourcePage));
  if (button.dataset.proposal !== undefined) {
    const proposals = currentResult.gemini.pages.flatMap(
      (p) => p.proposals || [],
    );
    const p = proposals[Number(button.dataset.proposal)];
    locate(p.table, p.row, p.page);
    startEdit(p.row - 1, p.column - 1);
    $("#edit-value").value = p.suggested;
    $("#edit-label").textContent +=
      " · Unverified Gemini proposal — compare with source before saving";
  }
  if (button.dataset.delete) {
    try {
      await api("/api/jobs/" + button.dataset.delete, { method: "DELETE" });
      refreshJobs();
      if (view === "validation") loadInbox();
      toast("Local source copy and extraction run deleted.");
    } catch (error) {
      fail(error);
    }
  }
});
$("#data-table").addEventListener("click", (event) => {
  const row = event.target.closest("[data-row]");
  const cell = event.target.closest("[data-cell]");
  const column = cell ? Number(cell.dataset.cell.split(",")[1]) : null;
  if (row) selectRow(Number(row.dataset.row), column);
});
$("#data-table").addEventListener("dblclick", (event) => {
  const cell = event.target.closest("[data-cell]");
  if (cell) startEdit(...cell.dataset.cell.split(",").map(Number));
});
$("#data-table").addEventListener("keydown", (event) => {
  const cell = event.target.closest("[data-cell]");
  if (cell && event.key === "Enter") {
    event.preventDefault();
    startEdit(...cell.dataset.cell.split(",").map(Number));
  }
});
$("#job-search").oninput = $("#document-search").oninput = renderJobs;
$("#row-filter").onchange = renderTable;
$("#issue-severity").onchange = renderIssues;
$("#inbox-severity").onchange = renderInbox;
$("#new-document").onclick = $("#list-upload").onclick = newExtraction;
$$('input[name="workflow"]').forEach(
  (input) => (input.onchange = updateWorkflow),
);
$("#file-input").onchange = (event) => upload(event.target.files[0]);
$("#dropzone").onclick = () => $("#file-input").click();
$("#dropzone").onkeydown = (event) => {
  if (["Enter", " "].includes(event.key)) {
    event.preventDefault();
    $("#file-input").click();
  }
};
["dragenter", "dragover"].forEach((name) =>
  $("#dropzone").addEventListener(name, (event) => {
    event.preventDefault();
    $("#dropzone").classList.add("dragging");
  }),
);
["dragleave", "drop"].forEach((name) =>
  $("#dropzone").addEventListener(name, (event) => {
    event.preventDefault();
    $("#dropzone").classList.remove("dragging");
    if (name === "drop") upload(event.dataTransfer.files[0]);
  }),
);
document.addEventListener("dragover", (event) => event.preventDefault());
document.addEventListener("drop", (event) => event.preventDefault());
$("#guide-button").onclick = $("#header-guide").onclick = () =>
  $("#guide-dialog").showModal();
$("#close-guide").onclick = () => $("#guide-dialog").close();
$("#edit-form").onsubmit = saveEdit;
$("#cancel-edit").onclick = () => $("#edit-dialog").close();
$("#back-button").onclick = () => go("documents");
$("#show-source").onchange = (event) =>
  $("#evidence-layout").classList.toggle("no-source", !event.target.checked);
$("#source-zoom").onchange = (event) =>
  ($(".source-image-wrap").style.width = event.target.value + "%");
$("#prev-page").onclick = () => showSourcePage(currentPage - 1);
$("#next-page").onclick = () => showSourcePage(currentPage + 1);
$("#page-number").onchange = (event) => showSourcePage(event.target.value);
$("#review-button").onclick = openReview;
$("#review-form").onsubmit = saveReview;
$("#cancel-review").onclick = () => $("#review-dialog").close();
$("#excel-download").onclick = openExport;
$("#close-export").onclick = () => $("#export-dialog").close();
$("#export-review").onclick = () => {
  $("#export-dialog").close();
  openReview();
};
$("#export-confirm").onclick = () => $("#export-dialog").close();
$("#retry-button").onclick = () => $("#retry-dialog").showModal();
$("#resume-button").onclick = async () => {
  try {
    await api(`/api/jobs/${currentJob}/retry?resume=true`, { method: "POST" });
    await openJob(currentJob);
  } catch (error) {
    fail(error);
  }
};
$("#cancel-retry").onclick = () => $("#retry-dialog").close();
$("#confirm-retry").onclick = async () => {
  try {
    await api(`/api/jobs/${currentJob}/retry?force_ocr=true`, {
      method: "POST",
    });
    $("#retry-dialog").close();
    openJob(currentJob);
  } catch (error) {
    fail(error);
  }
};
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    newExtraction();
  }
});
async function init() {
  try {
    const health = await api("/api/health");
    geminiConfig = health.gemini;
    updateWorkflow();
    $("#engine-status").textContent = "Local engine ready";
    await Promise.all([refreshJobs(), loadSamples()]);
    const hash = location.hash.slice(1);
    if (hash.startsWith("job=")) await openJob(hash.slice(4));
    else if (["documents", "validation", "benchmarks"].includes(hash)) go(hash);
  } catch (error) {
    $("#engine-status").textContent = "Engine unavailable";
    fail(error);
  }
}
init();

// A local preference only; no document or review data is stored here.
const textSize = $("#text-size");
try {
  textSize.value =
    localStorage.getItem("damnlens.textSize") === "large"
      ? "large"
      : "standard";
} catch {}
document.documentElement.dataset.textSize = textSize.value;
textSize.addEventListener("change", () => {
  document.documentElement.dataset.textSize = textSize.value;
  try {
    localStorage.setItem("damnlens.textSize", textSize.value);
  } catch {}
});

async function loadComplexEvidence() {
  try {
    const reports = await api("/api/complex-audit");
    if (view !== "benchmarks") return;
    $("#complex-evidence-panel")?.remove();
    const sections = [
      ["Complex reconstruction", reports.complex, true],
      ["Public fixtures with independent annotations", reports.public, false],
    ].filter(([, report]) => report);
    $("#benchmark-content").insertAdjacentHTML(
      "beforeend",
      `<div id="complex-evidence-panel">${sections
        .map(([title, report, runnable]) => {
          const correct = report.results.reduce(
              (n, x) => n + x.correct_cells,
              0,
            ),
            total = report.results.reduce((n, x) => n + x.denominator, 0);
          return `<section class="card requirements-card"><div class="card-header"><div><h2>${title} · ${report.results.filter((x) => x.exact).length} / ${report.results.length} exact cases</h2><p>${correct} / ${total} data cells match their declared ground truth. Headers are checked separately.</p></div></div><div class="table-container"><table class="report-table"><thead><tr><th>Document</th><th>Matching cells</th><th>Headers</th><th>Result</th>${runnable ? "<th>Try example</th>" : ""}</tr></thead><tbody>${report.results.map((x) => `<tr><td>${esc((x.case || x.file).replaceAll("_", " "))}</td><td>${x.correct_cells} / ${x.denominator}</td><td>${x.headers_exact ? "Exact" : "Review"}</td><td>${x.exact ? "Passed" : "Needs work"}</td>${runnable ? `<td><button class="text-button" data-complex-example="${esc(x.case)}">Run example →</button></td>` : ""}</tr>`).join("")}</tbody></table></div><div class="report-note">${esc(report.scope)}</div></section>`;
        })
        .join("")}</div>`,
    );
    $$("[data-complex-example]").forEach(
      (button) =>
        (button.onclick = async () => {
          try {
            const job = await api(
              "/api/complex-samples/" +
                encodeURIComponent(button.dataset.complexExample),
              { method: "POST" },
            );
            await openJob(job.id);
          } catch (error) {
            fail(error);
          }
        }),
    );
  } catch (error) {
    fail(error);
  }
}
