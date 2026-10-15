from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pymupdf as fitz
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .engine import extract, validate
from .exporter import xlsx, csv_bytes
from .quality import enrich, approve, revoke

ROOT = Path(__file__).resolve().parents[1]
JOBS = Path(os.environ.get("LEDGERLENS_DATA", ROOT / ".jobs"))
JOBS.mkdir(parents=True, exist_ok=True)
POOL = ThreadPoolExecutor(max_workers=1)
LOCK = threading.RLock()
app = FastAPI(title="LedgerLens", version="1.1.0", docs_url="/api/docs")
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
MAX_BYTES = 40 * 1024 * 1024


def job_dir(job):
    try:
        uuid.UUID(job)
    except ValueError:
        raise HTTPException(404, "Job not found")
    path = JOBS / job
    if not path.is_dir():
        raise HTTPException(404, "Job not found")
    return path


def save(path, data):
    with LOCK:
        temp = path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(data, ensure_ascii=False, allow_nan=False), encoding="utf-8"
        )
        temp.replace(path)


def load(path):
    with LOCK:
        return json.loads(path.read_text(encoding="utf-8"))


# A restart cannot leave an apparently running job forever.
for status in JOBS.glob("*/status.json"):
    data = load(status)
    if data["status"] in {"queued", "processing"}:
        data.update(
            status="interrupted",
            message="Processing interrupted by restart. Use retry to resume from the original document.",
        )
        save(status, data)


@app.middleware("http")
async def local_security(request: Request, call_next):
    host = request.headers.get("host", "").split(":")[0]
    if host not in {"localhost", "127.0.0.1", "testserver", "[::1]"}:
        return Response("Localhost access only", status_code=403)
    origin = request.headers.get("origin")
    if (
        request.method not in {"GET", "HEAD", "OPTIONS"}
        and origin
        and origin
        not in {
            f"http://{request.headers.get('host')}",
            f"https://{request.headers.get('host')}",
        }
    ):
        return Response("Cross-origin writes are disabled", status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )
    return response


def work(job):
    directory = job_dir(job)
    state = load(directory / "status.json")
    try:
        state.update(
            status="processing",
            message="Inspecting document",
            progress=0,
            stage="inspect",
            events=[],
        )
        save(directory / "status.json", state)

        def progress(done, total, message):
            state.update(progress=round(done / total * 92), message=message)
            save(directory / "status.json", state)

        def event(entry):
            state["events"].append(entry)
            state["stage"] = (
                "extract"
                if entry["stage"] == "inspect" and entry.get("page")
                else entry["stage"]
            )
            state["message"] = entry["message"] + (
                f" · page {entry['page']}" if entry.get("page") else ""
            )
            if state["stage"] in {"align", "validate", "review"}:
                state["progress"] = {"align": 94, "validate": 97, "review": 99}[
                    state["stage"]
                ]
            save(directory / "status.json", state)

        result = extract(
            directory / state["stored"],
            progress,
            force_ocr=state.get("force_ocr", False),
            event=event,
        )
        result["filename"] = state["filename"]
        save(directory / "result.json", result)
        state.update(
            status="complete",
            progress=100,
            message="Ready for review",
            rows=result["row_count"],
            tables=len(result["tables"]),
            issues=len(result["issues"]),
            page_count=result["page_count"],
            quality=result["quality"],
            review_status="pending",
            stage="review",
        )
    except Exception as exc:
        state.update(status="failed", message=str(exc)[:500])
    save(directory / "status.json", state)


def create_job(data, name, force=False):
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(415, "Use PDF, PNG, JPEG, TIFF, BMP or WebP.")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File exceeds the 40 MB limit.")
    try:
        with fitz.open(stream=data, filetype=ext.lstrip(".")) as doc:
            if doc.needs_pass:
                raise ValueError("Password-protected PDFs require an unlocked copy.")
            if not 1 <= len(doc) <= 50:
                raise ValueError("Documents must contain 1–50 pages.")
    except Exception as exc:
        raise HTTPException(422, f"Cannot open document: {exc}")
    job = str(uuid.uuid4())
    directory = JOBS / job
    directory.mkdir()
    stored = "source" + ext
    (directory / stored).write_bytes(data)
    state = {
        "id": job,
        "filename": Path(name.replace("\\", "/")).name,
        "stored": stored,
        "status": "queued",
        "progress": 0,
        "created": datetime.now(timezone.utc).isoformat(),
        "message": "Waiting for extraction",
        "force_ocr": force,
        "stage": "queued",
        "events": [],
        "attempt": 1,
        "review_status": "pending",
    }
    save(directory / "status.json", state)
    POOL.submit(work, job)
    return state


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": "1.1.0",
        "max_pages": 50,
        "max_upload_mb": 40,
        "ocr": "RapidOCR / ONNX CPU",
    }


@app.get("/api/jobs")
def jobs():
    listing = []
    for p in JOBS.glob("*/status.json"):
        state = load(p)
        if state["status"] == "complete" and (p.parent / "result.json").exists():
            r = enrich(load(p.parent / "result.json"))
            state.update(
                quality=r["quality"],
                review_status=r["quality"]["review_status"],
                page_count=r["page_count"],
            )
        listing.append(state)
    return sorted(listing, key=lambda d: d["created"], reverse=True)


@app.get("/api/review")
def review_inbox():
    findings = []
    for state in jobs():
        if state["status"] != "complete":
            continue
        r = enrich(load(JOBS / state["id"] / "result.json"))
        for issue in r["issues"]:
            page = issue.get("page")
            if not page and issue.get("table") and issue.get("row"):
                page = r["tables"][issue["table"] - 1]["rows"][issue["row"] - 1]["page"]
            findings.append(
                {
                    **issue,
                    "page": page,
                    "job": state["id"],
                    "filename": state["filename"],
                    "review_status": r["quality"]["review_status"],
                }
            )
    return findings


@app.post("/api/jobs", status_code=202)
async def upload(file: UploadFile = File(...), force_ocr: bool = False):
    data = await file.read(MAX_BYTES + 1)
    return create_job(data, file.filename or "document.pdf", force_ocr)


@app.get("/api/samples")
def samples():
    return [
        {"name": p.stem, "filename": p.name, "bytes": p.stat().st_size}
        for p in sorted((ROOT / "samples").glob("*.pdf"))
    ]


@app.get("/api/benchmark")
def benchmark():
    p = ROOT / "reports" / "benchmark.json"
    return load(p) if p.exists() else {"results": None}


@app.post("/api/samples/{name}", status_code=202)
def run_sample(name: str):
    if name not in {p.stem for p in (ROOT / "samples").glob("*.pdf")}:
        raise HTTPException(404, "Sample not found")
    p = ROOT / "samples" / f"{name}.pdf"
    return create_job(p.read_bytes(), p.name)


@app.get("/api/jobs/{job}")
def status(job: str):
    return load(job_dir(job) / "status.json")


@app.get("/api/jobs/{job}/result")
def result(job: str):
    directory = job_dir(job)
    if load(directory / "status.json")["status"] != "complete":
        raise HTTPException(409, "Extraction is not complete")
    p = directory / "result.json"
    if not p.exists():
        raise HTTPException(409, "Extraction is not complete")
    return enrich(load(p))


@app.post("/api/jobs/{job}/retry", status_code=202)
def retry(job: str, force_ocr: bool = False):
    with LOCK:
        directory = job_dir(job)
        state = load(directory / "status.json")
        if state["status"] in {"queued", "processing"}:
            raise HTTPException(409, "Already processing")
        if (directory / "result.json").exists():
            versions = directory / "versions"
            versions.mkdir(exist_ok=True)
            snapshot = enrich(load(directory / "result.json"))
            snapshot["saved_at"] = datetime.now(timezone.utc).isoformat()
            save(versions / f"{uuid.uuid4()}.json", snapshot)
            (directory / "result.json").unlink()
        state.update(
            status="queued",
            progress=0,
            message="Retry queued",
            force_ocr=force_ocr,
            stage="queued",
            events=[],
            attempt=state.get("attempt", 1) + 1,
            review_status="pending",
        )
        save(directory / "status.json", state)
    POOL.submit(work, job)
    return state


@app.get("/api/jobs/{job}/page/{page}")
def page_image(job: str, page: int):
    directory = job_dir(job)
    state = load(directory / "status.json")
    with fitz.open(directory / state["stored"]) as doc:
        if not doc.is_pdf:
            pdf = fitz.open("pdf", doc.convert_to_pdf())
            try:
                if page != 1:
                    raise HTTPException(404, "Page not found")
                png = pdf[0].get_pixmap(dpi=110, alpha=False).tobytes("png")
            finally:
                pdf.close()
        else:
            if not 1 <= page <= len(doc):
                raise HTTPException(404, "Page not found")
            png = doc[page - 1].get_pixmap(dpi=110, alpha=False).tobytes("png")
    return Response(png, media_type="image/png")


class Correction(BaseModel):
    table: int = Field(ge=1)
    row: int = Field(ge=1)
    column: int = Field(ge=1)
    value: str = Field(max_length=10000)


@app.patch("/api/jobs/{job}/cells")
def correct(job: str, edit: Correction):
    with LOCK:
        directory = job_dir(job)
        r = result(job)
        try:
            table = r["tables"][edit.table - 1]
            row = table["rows"][edit.row - 1]
            before = row["cells"][edit.column - 1]
        except IndexError:
            raise HTTPException(404, "Cell not found")
        if before == edit.value:
            return r
        row["cells"][edit.column - 1] = edit.value
        r["edits"].append(
            {
                **edit.model_dump(exclude={"value"}),
                "before": before,
                "after": edit.value,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        r["issues"] = validate(r["tables"]) + [
            i for i in r["issues"] if i["kind"] == "page_review"
        ]
        revoke(r, "Data changed; review must be completed again.")
        r.setdefault("events", []).append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "stage": "review",
                "message": f"Cell corrected; table {edit.table}, row {edit.row}, column {edit.column}. Validation refreshed.",
                "page": row["page"],
            }
        )
        save(directory / "result.json", r)
        state = load(directory / "status.json")
        state["issues"] = len(r["issues"])
        state.update(quality=r["quality"], review_status="pending")
        save(directory / "status.json", state)
        return r


class Review(BaseModel):
    note: str = Field(default="", max_length=5000)
    accept_findings: bool = False
    source_checked: bool = False


@app.post("/api/jobs/{job}/review")
def complete_review(job: str, review: Review):
    with LOCK:
        if not review.source_checked:
            raise HTTPException(
                422, "Confirm that source values and column alignment were checked."
            )
        directory = job_dir(job)
        r = result(job)
        try:
            approve(r, review.note, review.accept_findings)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        r.setdefault("events", []).append(
            {
                "at": r["review"]["at"],
                "stage": "review",
                "message": f"Human review completed; {r['review']['accepted_findings']} findings accepted."
                + (" Note: " + review.note if review.note else ""),
            }
        )
        save(directory / "result.json", r)
        state = load(directory / "status.json")
        state.update(quality=r["quality"], review_status="reviewed")
        save(directory / "status.json", state)
        return r


@app.get("/api/jobs/{job}/versions")
def versions(job: str):
    items = [
        {
            "id": p.stem,
            "saved_at": r.get("saved_at"),
            "rows": r["row_count"],
            "edits": len(r["edits"]),
            "review_status": enrich(r)["quality"]["review_status"],
        }
        for p in sorted((job_dir(job) / "versions").glob("*.json"), reverse=True)
        for r in [load(p)]
    ]
    return sorted(items, key=lambda item: item["saved_at"] or "", reverse=True)


@app.get("/api/jobs/{job}/versions/{version}/export/{kind}")
def version_export(job: str, version: str, kind: str):
    try:
        uuid.UUID(version)
    except ValueError:
        raise HTTPException(404, "Saved run not found")
    p = job_dir(job) / "versions" / f"{version}.json"
    if not p.exists():
        raise HTTPException(404, "Saved run not found")
    r = enrich(load(p))
    if kind == "xlsx":
        return Response(
            xlsx(r),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": 'attachment; filename="ledgerlens-previous-run.xlsx"'
            },
        )
    if kind == "json":
        return Response(
            json.dumps(r, indent=2).encode(),
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="ledgerlens-previous-run.json"'
            },
        )
    raise HTTPException(404, "Unknown format")


@app.get("/api/jobs/{job}/export/{kind}")
def export(job: str, kind: str, table: int = 1):
    r = result(job)
    if kind == "xlsx":
        data = xlsx(r)
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif kind == "json":
        data = json.dumps(r, ensure_ascii=False, indent=2).encode()
        mime = "application/json"
    elif kind == "csv":
        if not 1 <= table <= len(r["tables"]):
            raise HTTPException(404, "Table not found")
        data = csv_bytes(r["tables"][table - 1])
        mime = "text/csv"
    else:
        raise HTTPException(404, "Unknown format")
    return Response(
        data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="ledgerlens.{kind}"'},
    )


@app.delete("/api/jobs/{job}", status_code=204)
def delete(job: str):
    with LOCK:
        directory = job_dir(job)
        if load(directory / "status.json")["status"] in {"queued", "processing"}:
            raise HTTPException(409, "Wait for processing to finish")
        shutil.rmtree(directory)
    return Response(status_code=204)


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
