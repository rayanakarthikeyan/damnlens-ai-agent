"""Separate private-demo entry point; existing localhost OCR API is unchanged."""

from __future__ import annotations

import hmac
import logging
import os
import re
import threading
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from .research import DenseEncoder, ResearchError, ResearchStore

LOG = logging.getLogger("damnlens.research")


class Page(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(ge=1, le=50)
    text: str = Field(min_length=1, max_length=24000)


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document: str = Field(min_length=1, max_length=120, pattern=r"^[\w .()-]+$")
    pages: list[Page] = Field(min_length=1, max_length=50)


class Ingest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    documents: list[Document] = Field(min_length=1, max_length=10)


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=1000)
    provider: str = Field(default="extractive", pattern=r"^(extractive|gemini)$")
    cloud_consent: bool = False


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    note: str = Field(min_length=10, max_length=1500)


def create_app(data=None, token=None, encoder=None, rate_limit=60):
    data = Path(data or os.environ.get("RESEARCH_DATA", ".research"))
    secret = token or os.environ.get("RESEARCH_TOKEN", "")
    if len(secret) < 32:
        raise RuntimeError(
            "Set RESEARCH_TOKEN to a random secret of at least 32 characters"
        )
    store = ResearchStore(
        data / "research.sqlite3", encoder or DenseEncoder(data / "models")
    )
    app = FastAPI(title="DamnLens Research", version="0.1.0")
    app.state.store = store
    lock = threading.Lock()
    limiters = {}
    capacity = threading.BoundedSemaphore(2)

    @app.middleware("http")
    async def protect(request: Request, call_next):
        started = time.perf_counter()
        public = request.url.path in {"/", "/healthz", "/research.js", "/research.css"}
        if not public:
            if not hmac.compare_digest(
                request.headers.get("authorization", ""), "Bearer " + secret
            ):
                return JSONResponse(
                    {"detail": "Valid bearer token required"}, status_code=401
                )
            try:
                if int(request.headers.get("content-length", "0")) > 6 * 1024 * 1024:
                    return JSONResponse(
                        {"detail": "Request exceeds 6 MB"}, status_code=413
                    )
            except ValueError:
                return JSONResponse(
                    {"detail": "Invalid content length"}, status_code=400
                )
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
                return JSONResponse(
                    {"detail": "Cross-origin API calls disabled"}, status_code=403
                )
            now = time.monotonic()
            with lock:
                # One shared private workspace and token; limit all requests together.
                times = [t for t in limiters.get("workspace", []) if now - t < 60]
                if len(times) >= rate_limit:
                    return JSONResponse(
                        {"detail": "Request budget reached"}, status_code=429
                    )
                limiters["workspace"] = [*times, now]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
        )
        LOG.info(
            "request method=%s status=%s elapsed_ms=%.1f",
            request.method,
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        return response

    @app.exception_handler(ResearchError)
    async def bad_research(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    def collection_id(value):
        if not re.fullmatch(r"[a-z0-9-]{1,48}", value):
            raise HTTPException(
                422,
                "Use a collection name containing lowercase letters, numbers or hyphens",
            )
        return value

    def bounded(fn, *args):
        if not capacity.acquire(blocking=False):
            raise HTTPException(429, "Processing capacity reached; try later")
        try:
            return fn(*args)
        finally:
            capacity.release()

    @app.get("/healthz")
    def health():
        return {"status": "ok", "version": app.version}

    @app.get("/")
    def home():
        return FileResponse(Path(__file__).parents[1] / "web/research.html")

    @app.get("/research.js")
    def javascript():
        return FileResponse(
            Path(__file__).parents[1] / "web/research.js", media_type="text/javascript"
        )

    @app.get("/research.css")
    def css():
        return FileResponse(
            Path(__file__).parents[1] / "web/research.css", media_type="text/css"
        )

    @app.post("/v1/collections/{collection}/documents")
    def ingest(collection: str, payload: Ingest):
        return bounded(
            store.index,
            collection_id(collection),
            [d.model_dump() for d in payload.documents],
        )

    @app.post("/v1/collections/{collection}/upload")
    def upload(collection: str, file: UploadFile = File(...)):
        collection_id(collection)
        raw = file.file.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            raise HTTPException(413, "Upload exceeds 5 MB")
        name = Path((file.filename or "document.txt").replace("\\", "/")).name
        if name.lower().endswith(".pdf"):
            import pymupdf

            try:
                with pymupdf.open(stream=raw, filetype="pdf") as pdf:
                    if pdf.needs_pass or not 1 <= len(pdf) <= 50:
                        raise ValueError()
                    pages = [
                        {"page": i + 1, "text": page.get_text()}
                        for i, page in enumerate(pdf)
                    ]
                if any(not p["text"].strip() for p in pages):
                    raise HTTPException(
                        422, "Image-only pages require OCR first; no pages were indexed"
                    )
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(
                    422, "Use an unlocked readable PDF of 1-50 pages"
                ) from None
        elif name.lower().endswith((".txt", ".md")):
            try:
                pages = [{"page": 1, "text": raw.decode("utf-8")}]
            except UnicodeDecodeError:
                raise HTTPException(422, "Text must be UTF-8") from None
        else:
            raise HTTPException(415, "Use PDF, TXT or Markdown")
        try:
            document = Document(document=name, pages=pages)
        except ValueError:
            raise HTTPException(
                422, "Invalid filename, page length or empty text"
            ) from None
        return bounded(store.index, collection, [document.model_dump()])

    @app.post("/v1/collections/{collection}/runs")
    def ask(collection: str, payload: Question):
        return bounded(
            store.start,
            collection_id(collection),
            payload.question,
            payload.provider,
            payload.cloud_consent,
        )

    @app.get("/v1/runs/{run_id}")
    def get_run(run_id: str):
        try:
            return store.get(run_id)
        except KeyError:
            raise HTTPException(404, "Run not found") from None

    @app.post("/v1/runs/{run_id}/approve")
    def approve(run_id: str, payload: Approval):
        get_run(run_id)
        return store.approve(run_id, payload.evidence_sha256, payload.note)

    @app.get("/v1/runs/{run_id}/export")
    def export(run_id: str):
        run = get_run(run_id)
        if run["status"] != "approved":
            raise HTTPException(
                409, "Review and approve the evidence snapshot before exporting"
            )
        text = ["# Reviewed research brief", "", "Question: " + run["question"], ""]
        for claim in run["claims"]:
            text.append(
                f"- {claim['quote']} [{claim['document']}, page {claim['page']}, {claim['source_id']}]"
            )
        if run["suggested_angle"]:
            text.extend(
                ["", "## Suggested angle (reviewed hypothesis)", run["suggested_angle"]]
            )
        text.extend(
            [
                "",
                "Reviewer note: " + run["review"]["note"],
                "Evidence SHA-256: " + run["evidence_sha256"],
            ]
        )
        return PlainTextResponse(
            "\n".join(text),
            headers={"Content-Disposition": 'attachment; filename="reviewed-brief.md"'},
        )

    return app
