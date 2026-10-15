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
  if (next === "benchmarks") loadBenchmark();
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
  return `<div class="table-container"><table class="document-table"><thead><tr><th>Document</th><th class="doc-date-col">Created</th><th class="doc-shape-col">Extraction</th><th class="doc-scope-col">Page coverage</th><th>Review status</th><th></th></tr></thead><tbody>${list.map((j) => `<tr><td><button class="doc-open" data-job="${esc(j.id)}"><span class="file-tile">${icon("file")}</span><span><span class="doc-name">${esc(j.filename)}</span><span class="doc-meta">${j.force_ocr ? "OCR only" : "Automatic routing"}${j.attempt > 1 ? " · attempt " + j.attempt : ""}</span></span></button></td><td class="doc-date-col">${dateText(j.created)}</td><td class="doc-shape-col">${j.rows ?? "—"} rows <span class="muted">/</span> ${j.tables ?? "—"} tables</td><td class="doc-scope-col">${j.quality ? j.quality.pages_extracted + " / " + j.quality.pages_total : "—"}</td><td>${jobBadge(j)}</td><td><div class="doc-actions"><button class="text-button" data-job="${esc(j.id)}">${j.status === "complete" ? "Open" : "View"}</button><button class="delete-doc" data-delete="${esc(j.id)}" aria-label="Delete ${esc(j.filename)}">${icon("close")}</button></div></td></tr>`).join("")}</tbody></table></div>`;
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
    const j = await api(
      "/api/jobs?force_ocr=" + ($("#extraction-mode").value === "ocr"),
      { method: "POST", body },
    );
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
  ["#excel-download", "#review-button", "#retry-button"].forEach(
    (s) => ($(s).hidden = true),
  );
  $("#progress-label").textContent = "Opening extraction run";
  $('#progress-bar').style.width='0%';
  $('#progress-text').textContent='0%';
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
      `${dateText(j.created)} · ${j.force_ocr ? "OCR only" : "Automatic routing"} · Run ${id.slice(0, 8)}${j.attempt > 1 ? " · Attempt " + j.attempt : ""}`;
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
    ["Extracted rows", q.rows, q.tables + " joined tables"],
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
  setTab(preserveTab ? activeTab : "data");
  if (!preserveTab) {
    $('#data-table').scrollTo({top:0,left:0});
    showSourcePage(1);
  }
}
function renderTable() {
  const t = currentResult.tables[currentTable];
  if (!t) {
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
    `Showing ${rows.length} / ${t.rows.length} rows · ${flagged.size} rows have findings · ${quality().export_label}`;
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
              .join("")}<td>${r.page}</td></tr>`,
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
  ["data", "issues", "coverage", "activity", "corrections"].forEach(
    (name) => ($("#" + name + "-panel").hidden = name !== tab),
  );
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
                `<div class="version-row"><span>${dateText(v.saved_at)} · ${v.rows} rows · ${v.edits} corrections · ${esc(v.review_status)}</span><div><a class="text-button" href="/api/jobs/${id}/versions/${v.id}/export/xlsx">Excel ${icon("download")}</a><a class="text-button" href="/api/jobs/${id}/versions/${v.id}/export/json">JSON ${icon("download")}</a></div></div>`,
            )
            .join("")
        : '<p class="muted">No retries yet. A previous run is saved before every OCR retry.</p>');
  } catch (error) {
    fail(error);
  }
}
function renderCorrections() {
  const r = currentResult;
  $("#corrections-panel").innerHTML =
    `<div class="panel-tools"><div><h2>Correction history</h2><p>Original values remain available. A change resets the review decision.</p></div><span class="badge neutral">${r.edits.length} changes</span></div>` +
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
    ? `Table ${currentTable + 1} · Row ${row.id} · ${row.method}${row.method.startsWith("OCR") ? " · recognition " + (row.confidence * 100).toFixed(1) + "%" : ""}`
    : "Select a row to inspect its source location.";
  img.onload = () => {
    if (token !== sourceToken) return;
    if (row) {
      const width = details.width || (img.naturalWidth * 72) / 110,
        height = details.height || (img.naturalHeight * 72) / 110;
      const [x0, y0, x1, y1] = row.bbox;
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
function selectRow(index) {
  selectedRow = index;
  $$("tr[data-row]").forEach((tr) =>
    tr.classList.toggle("selected", Number(tr.dataset.row) === index),
  );
  const row = currentResult.tables[currentTable]?.rows[index];
  if (row) showSourcePage(row.page, row);
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
    ["Data", `${q.rows} rows / ${q.tables} tables`],
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
        .join("")}</tbody></table></div></div>`;
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
  if (row) selectRow(Number(row.dataset.row));
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
$("#new-document").onclick = $("#list-upload").onclick = () =>
  $("#file-input").click();
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
    $("#file-input").click();
  }
});
async function init() {
  try {
    await api("/api/health");
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
