"use strict";
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const icon = (name) => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
let jobs = [],
  currentJob = null,
  currentResult = null,
  currentTable = 0,
  currentPage = 1,
  selectedRow = null,
  pollTimer = null,
  editCell = null,
  view = "workspace";
let toastTimer;
function toast(message) {
  $("#toast").textContent = message;
  $("#toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("#toast").hidden = true), 6500);
}
async function api(url, options = {}) {
  const r = await fetch(url, options);
  if (!r.ok) {
    let detail;
    try {
      detail = (await r.json()).detail;
    } catch {
      detail = r.statusText;
    }
    throw Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return r.status === 204 ? null : r.json();
}
function reportError(error) {
  toast(error.message || "Something went wrong. Please retry.");
  console.error(error);
}
function go(next) {
  view = next;
  clearTimeout(pollTimer);
  $$("#main>section").forEach((el) => (el.hidden = true));
  const ids = {
    workspace: "home-view",
    documents: "list-view",
    validation: "review-view",
    benchmarks: "benchmark-view",
    result: "result-view",
  };
  $("#" + ids[next]).hidden = false;
  window.scrollTo({ top: 0 });
  $$(".nav-item").forEach((el) =>
    el.classList.toggle("active", el.dataset.view === next),
  );
  $("#breadcrumb").textContent = {
    workspace: "Overview",
    documents: "All documents",
    validation: "Review center",
    benchmarks: "Accuracy report",
    result: "Extraction review",
  }[next];
  if (next === "benchmarks") loadBenchmark();
  if (next !== "result") {
    history.replaceState(null, "", "#" + next);
    refreshJobs();
  }
}
function dateText(s) {
  return new Date(s).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
function renderJobList(list) {
  if (!list.length)
    return `<div class="empty-state">${icon("file")}Your first extraction starts here. Upload a document or try a sample.</div>`;
  return (
    '<div class="doc-list">' +
    list
      .map(
        (j) =>
          `<div class="doc-row"><button class="doc-open" data-job="${esc(j.id)}">${icon("file")}<span><span class="doc-name">${esc(j.filename)}</span><span class="doc-meta">${dateText(j.created)} ${j.force_ocr ? "· OCR forced" : ""}</span></span></button><span class="badge ${j.status === "complete" ? (j.issues ? "warning" : "success") : ["failed", "interrupted"].includes(j.status) ? "error" : "neutral"}">${esc(j.status === "complete" ? (j.issues ? j.issues + " to review" : "Ready to export") : j.status)}</span><span class="doc-meta doc-count-text">${j.rows ?? "—"} rows · ${j.tables ?? "—"} tables</span><button class="delete-doc" data-delete="${esc(j.id)}" aria-label="Delete ${esc(j.filename)}">${icon("x")}</button></div>`,
      )
      .join("") +
    "</div>"
  );
}
async function refreshJobs() {
  try {
    jobs = await api("/api/jobs");
    $("#doc-count").textContent = jobs.length;
    $("#issue-count").textContent = jobs.reduce(
      (a, j) => a + (j.issues || 0),
      0,
    );
    $("#recent-list").innerHTML = renderJobList(jobs.slice(0, 4));
    $("#document-list").innerHTML = renderJobList(jobs);
    $("#review-list").innerHTML = renderJobList(
      jobs.filter(
        (j) => j.issues || ["failed", "interrupted"].includes(j.status),
      ),
    );
  } catch (e) {
    reportError(e);
  }
}
const sampleMeta = {
  "01_invoice_register": {
    title: "The invoice register",
    subtitle: "3 pages · 12 columns · Digital PDF",
    tags: ["Multi-page", "Repeated headers"],
  },
  "02_scanned_inventory": {
    title: "The scanned inventory",
    subtitle: "2 pages · 12 columns · Image-only PDF",
    tags: ["OCR", "Wide tables"],
  },
  "03_bank_statement": {
    title: "The bank statement",
    subtitle: "2 pages · 12 columns · Deliberate errors",
    tags: ["Validation", "Missing values"],
  },
};
async function loadSamples() {
  const samples = await api("/api/samples");
  $("#sample-cards").innerHTML = samples
    .map((s) => {
      const m = sampleMeta[s.name] || {
        title: s.filename,
        subtitle: "Sample document",
        tags: ["Try extraction"],
      };
      return `<button class="sample-card" data-sample="${esc(s.name)}"><div class="sample-top">${icon(s.name.includes("scanned") ? "scan" : "file")}<div><strong>${esc(m.title)}</strong><p>${esc(m.subtitle)}</p></div></div><div class="sample-tags">${m.tags.map((t) => `<span>${esc(t)}</span>`).join("")}</div>${icon("arrow")}</button>`;
    })
    .join("");
}
async function upload(file) {
  if (!file) return;
  if (file.size > 40 * 1024 * 1024) {
    toast("Please choose a file smaller than 40 MB.");
    return;
  }
  const data = new FormData();
  data.append("file", file);
  try {
    toast("Document added. Starting extraction…");
    const j = await api("/api/jobs?force_ocr=" + $("#force-ocr").checked, {
      method: "POST",
      body: data,
    });
    await openJob(j.id);
  } catch (e) {
    reportError(e);
  } finally {
    $("#file-input").value = "";
  }
}
async function runSample(name) {
  try {
    toast("Starting a real extraction of the sample…");
    const j = await api("/api/samples/" + encodeURIComponent(name), {
      method: "POST",
    });
    await openJob(j.id);
  } catch (e) {
    reportError(e);
  }
}
async function openJob(id) {
  currentJob = id;
  currentResult = null;
  currentTable = 0;
  selectedRow = null;
  go("result");
  history.replaceState(null, "", "#job=" + id);
  $("#processing").hidden = false;
  $("#result-content").hidden = true;
  $("#excel-download").hidden = true;
  $("#retry-button").hidden = true;
  await pollJob();
}
async function pollJob() {
  try {
    const id = currentJob;
    const j = await api(`/api/jobs/${id}`);
    if (id !== currentJob || view !== "result") return;
    $("#result-title").textContent = j.filename;
    $("#result-subtitle").textContent =
      `${dateText(j.created)} · Processed privately on this computer`;
    $("#progress-label").textContent = j.message;
    $("#progress-bar").style.width = j.progress + "%";
    $("#progress-text").textContent = j.progress + "%";
    if (j.status === "complete") {
      currentResult = await api(`/api/jobs/${id}/result`);
      if (id !== currentJob) return;
      renderResult();
      refreshJobs();
    } else if (["failed", "interrupted"].includes(j.status)) {
      $("#progress-label").textContent =
        j.status === "failed"
          ? "Extraction needs attention"
          : "Extraction interrupted";
      $("#processing .muted").textContent = j.message;
      $("#retry-button").hidden = false;
      toast(j.message);
      refreshJobs();
    } else {
      pollTimer = setTimeout(pollJob, 800);
    }
  } catch (e) {
    reportError(e);
    pollTimer = setTimeout(pollJob, 2500);
  }
}
function renderResult() {
  const r = currentResult;
  $("#processing").hidden = true;
  $("#result-content").hidden = false;
  $("#excel-download").hidden = false;
  $("#retry-button").hidden = false;
  $("#excel-download").href = `/api/jobs/${currentJob}/export/xlsx`;
  $("#json-download").href = `/api/jobs/${currentJob}/export/json`;
  $("#csv-download").href =
    `/api/jobs/${currentJob}/export/csv?table=${currentTable + 1}`;
  $("#result-metrics").innerHTML = [
    [
      "Pages",
      r.page_count,
      r.pages.filter((p) => p.method === "ocr").length + " read with OCR",
    ],
    ["Tables", r.tables.length, "Joined across adjacent pages"],
    ["Rows", r.row_count, "Data rows preserved"],
    [
      "Findings",
      r.issues.length,
      r.issues.filter((i) => i.severity === "error").length +
        " errors to inspect",
    ],
    [
      "Processing",
      r.elapsed_seconds + "s",
      r.headers_removed + " repeated headers removed",
    ],
  ]
    .map(
      ([label, value, note]) =>
        `<div class="metric"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(note)}</small></div>`,
    )
    .join("");
  $("#finding-count").textContent = r.issues.length;
  $("#table-selectors").innerHTML = r.tables
    .map(
      (t, i) =>
        `<button data-table="${i}" class="${i === currentTable ? "active" : ""}">${esc(t.name)} <small>· ${t.rows.length} rows</small></button>`,
    )
    .join("");
  renderTable();
  renderIssues();
  renderActivity();
  setTab("data");
  showSourcePage(1);
}
function renderTable() {
  const t = currentResult.tables[currentTable];
  if (!t) {
    $("#data-table").innerHTML =
      '<div class="empty-state">No tables were detected. Open validation to inspect page-level findings, or retry with OCR.</div>';
    return;
  }
  $("#csv-download").href = `/api/jobs/${currentJob}/export/csv?table=${t.id}`;
  $("#data-table").innerHTML =
    `<table class="data-table"><thead><tr><th>#</th>${t.headers.map((h) => `<th>${esc(h)}</th>`).join("")}<th>Page</th></tr></thead><tbody>${t.rows
      .map(
        (r, i) =>
          `<tr data-row="${i}" ${selectedRow === i ? 'class="selected"' : ""}><td>${r.id}</td>${r.cells
            .map((c, col) => {
              const issues = currentResult.issues.filter(
                (a) =>
                  a.table === t.id &&
                  a.row === r.id &&
                  (!a.column || a.column === col + 1),
              );
              return `<td data-cell="${i},${col}" tabindex="0" class="${issues.length ? "flagged" : ""} ${issues.some((a) => a.severity === "error") ? "error" : ""}" title="${esc(issues.map((i) => i.message).join("\n") || "Double-click or press Enter to edit")}">${esc(c) || '<span class="muted">—</span>'}</td>`;
            })
            .join("")}<td>${r.page}</td></tr>`,
      )
      .join("")}</tbody></table>`;
  $$("[data-table]").forEach((b) =>
    b.classList.toggle("active", Number(b.dataset.table) === currentTable),
  );
}
function setTab(tab) {
  $$("[data-tab]").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tab);
    b.setAttribute("aria-selected", b.dataset.tab === tab);
  });
  ["data", "issues", "activity"].forEach(
    (t) => ($("#" + t + "-panel").hidden = t !== tab),
  );
}
function renderIssues() {
  const issues = currentResult.issues;
  $("#issues-panel").innerHTML = issues.length
    ? issues
        .map(
          (i) =>
            `<article class="finding ${esc(i.severity)}">${icon(i.severity === "error" ? "alert" : "shield")}<div class="finding-content"><h3>${esc(i.kind.replaceAll("_", " "))} ${i.table ? `<span class="badge neutral">TABLE ${i.table}${i.row ? " · ROW " + i.row : ""}${i.column ? " · COL " + i.column : ""}</span>` : ""}</h3><p>${esc(i.message)}</p></div>${i.table && i.row ? `<button class="text-button" data-finding="${i.table},${i.row}">Locate ${icon("arrow")}</button>` : ""}</article>`,
        )
        .join("")
    : `<div class="empty-state">${icon("shield")}No issues found by the implemented checks. Review critical numbers against the source before use.</div>`;
}
function renderActivity() {
  const r = currentResult;
  $("#activity-panel").innerHTML =
    `<div class="timeline">${r.pages.map((p) => `<div class="timeline-entry"><span>${icon(p.status === "extracted" ? "check" : "alert")}</span><div><strong>Page ${p.page} · ${p.status === "extracted" ? p.tables + " table fragment" + (p.tables === 1 ? "" : "s") : "Needs review"}</strong><p>${esc(p.attempts.join(" → "))}</p><small>${p.method === "ocr" ? "Local OCR recognition + layout reconstruction" : "Native PDF text + table detection"}</small></div></div>`).join("")}<div class="timeline-entry"><span>${icon("link")}</span><div><strong>Stitched ${r.tables.length} tables · removed ${r.headers_removed} repeated headers</strong><p>Legitimate duplicate data rows are preserved and flagged.</p></div></div><div class="timeline-entry"><span>${icon("shield")}</span><div><strong>Validation complete · ${r.issues.length} findings</strong><p>${r.edits.length} manual correction${r.edits.length === 1 ? "" : "s"} recorded. Correction history is included in Excel and JSON.</p><small>SHA-256: ${esc(r.sha256)}</small></div></div></div>`;
}
function showSourcePage(page, row = null) {
  if (!currentResult) return;
  currentPage = Math.max(1, Math.min(currentResult.page_count, page));
  $("#source-image").src = `/api/jobs/${currentJob}/page/${currentPage}`;
  $("#source-page-label").textContent =
    `Page ${currentPage} / ${currentResult.page_count}`;
  $("#prev-page").disabled = currentPage === 1;
  $("#next-page").disabled = currentPage === currentResult.page_count;
  $("#source-highlight").hidden = true;
  $("#source-caption").textContent = row
    ? `Row ${row.id} · ${row.method}${row.method.startsWith("OCR") ? " · recognition score " + Math.round(row.confidence * 100) + "%" : ""}`
    : "Select a row to see its source region.";
  if (row) {
    $("#source-image").onload = () => {
      const img = $("#source-image");
      const pdfWidth = (img.naturalWidth * 72) / 110;
      const pdfHeight = (img.naturalHeight * 72) / 110;
      const [x0, y0, x1, y1] = row.bbox;
      const box = $("#source-highlight");
      Object.assign(box.style, {
        left: (x0 / pdfWidth) * 100 + "%",
        top: (y0 / pdfHeight) * 100 + "%",
        width: ((x1 - x0) / pdfWidth) * 100 + "%",
        height: ((y1 - y0) / pdfHeight) * 100 + "%",
      });
      box.hidden = false;
      box.scrollIntoView({ behavior: "smooth", block: "nearest" });
    };
    if ($("#source-image").complete) $("#source-image").onload();
  } else {
    $("#source-image").onload = null;
  }
}
function selectRow(idx) {
  selectedRow = idx;
  $$(".data-table tr[data-row]").forEach((tr) =>
    tr.classList.toggle("selected", Number(tr.dataset.row) === idx),
  );
  const row = currentResult.tables[currentTable]?.rows[idx];
  if (row) showSourcePage(row.page, row);
}
function startEdit(row, col) {
  editCell = { row, col };
  const t = currentResult.tables[currentTable];
  $("#edit-label").textContent =
    `${t.name} · Row ${row + 1} · ${t.headers[col]}`;
  $("#edit-value").value = t.rows[row].cells[col];
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
    renderResult();
    toast("Correction saved. Validation has been refreshed.");
  } catch (e) {
    reportError(e);
  }
}
async function loadBenchmark() {
  try {
    const r = await api("/api/benchmark");
    if (!r.results) {
      $("#benchmark-content").innerHTML =
        '<div class="empty-state">Run python scripts/benchmark.py to generate the reproducible accuracy report.</div>';
      return;
    }
    $("#benchmark-content").innerHTML =
      `<table class="report-table"><thead><tr><th>Fixture</th><th>Pages</th><th>Cells correct</th><th>Row recall</th><th>Seconds</th></tr></thead><tbody>${r.results.map((a) => `<tr><td>${esc(a.file)}</td><td>${a.pages}</td><td>${a.correct_cells} / ${a.expected_cells}<br><strong>${(a.cell_accuracy * 100).toFixed(2)}%</strong></td><td>${(a.row_recall * 100).toFixed(1)}%</td><td>${a.seconds}</td></tr>`).join("")}</tbody></table><div class="report-note"><strong>How we measure.</strong> ${esc(r.methodology)}<br><br>Generated ${esc(r.generated)}. ${esc(r.limitations)}<br><br>OCR recognition scores in the review workspace are separate from this measured cell accuracy.</div>`;
  } catch (e) {
    reportError(e);
  }
}
document.addEventListener("click", async (e) => {
  const b = e.target.closest("button,a");
  if (!b) return;
  if (b.dataset.view) go(b.dataset.view);
  if (b.dataset.sample) runSample(b.dataset.sample);
  if (b.dataset.job) openJob(b.dataset.job);
  if (b.dataset.table !== undefined) {
    currentTable = Number(b.dataset.table);
    selectedRow = null;
    renderTable();
  }
  if (b.dataset.tab) setTab(b.dataset.tab);
  if (b.dataset.finding) {
    const [t, r] = b.dataset.finding.split(",").map(Number);
    currentTable = t - 1;
    renderTable();
    setTab("data");
    selectRow(r - 1);
    $(`[data-row="${r - 1}"]`)?.scrollIntoView({ block: "nearest" });
  }
  if (b.dataset.delete) {
    try {
      await api("/api/jobs/" + b.dataset.delete, { method: "DELETE" });
      refreshJobs();
      toast("Document and local extraction files deleted.");
    } catch (e) {
      reportError(e);
    }
  }
});
$("#data-table").addEventListener("click", (e) => {
  const tr = e.target.closest("[data-row]");
  if (tr) selectRow(Number(tr.dataset.row));
});
$("#data-table").addEventListener("dblclick", (e) => {
  const td = e.target.closest("[data-cell]");
  if (td) startEdit(...td.dataset.cell.split(",").map(Number));
});
$("#data-table").addEventListener("keydown", (e) => {
  const td = e.target.closest("[data-cell]");
  if (td && e.key === "Enter") {
    e.preventDefault();
    startEdit(...td.dataset.cell.split(",").map(Number));
  }
});
$("#edit-form").addEventListener("submit", saveEdit);
$("#cancel-edit").onclick = () => $("#edit-dialog").close();
$("#new-document").onclick = $("#list-upload").onclick = () =>
  $("#file-input").click();
$("#file-input").onchange = (e) => upload(e.target.files[0]);
$("#dropzone").onclick = () => $("#file-input").click();
$("#dropzone").onkeydown = (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    $("#file-input").click();
  }
};
["dragenter", "dragover"].forEach((ev) =>
  $("#dropzone").addEventListener(ev, (e) => {
    e.preventDefault();
    $("#dropzone").classList.add("dragging");
  }),
);
["dragleave", "drop"].forEach((ev) =>
  $("#dropzone").addEventListener(ev, (e) => {
    e.preventDefault();
    $("#dropzone").classList.remove("dragging");
    if (ev === "drop") upload(e.dataTransfer.files[0]);
  }),
);
document.addEventListener("dragover", (e) => e.preventDefault());
document.addEventListener("drop", (e) => e.preventDefault());
$("#guide-button").onclick = () => $("#guide-dialog").showModal();
$("#close-guide").onclick = () => $("#guide-dialog").close();
$("#back-button").onclick = () => go("workspace");
$("#show-source").onchange = (e) =>
  $("#evidence-layout").classList.toggle("no-source", !e.target.checked);
$("#prev-page").onclick = () => showSourcePage(currentPage - 1);
$("#next-page").onclick = () => showSourcePage(currentPage + 1);
$("#retry-button").onclick = async () => {
  try {
    await api(`/api/jobs/${currentJob}/retry?force_ocr=true`, {
      method: "POST",
    });
    openJob(currentJob);
  } catch (e) {
    reportError(e);
  }
};
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
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
  } catch (e) {
    $("#engine-status").textContent = "Engine unavailable";
    reportError(e);
  }
}
init();
