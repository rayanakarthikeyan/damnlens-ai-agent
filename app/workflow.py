"""Two explicit workflows sharing one local extraction and validation baseline."""

import time

import pymupdf as fitz

from .engine import extract
from .gemini import GeminiError, assist, configuration, review_issues
from .quality import enrich


def options(mode="local", cloud_consent=False, scope="flagged", max_requests=3):
    if mode not in {"local", "gemini"} or scope not in {"flagged", "all"}:
        raise ValueError("Choose a supported workflow and page selection.")
    if type(max_requests) is not int or not 1 <= max_requests <= 50:
        raise ValueError("Gemini request limit must be between 1 and 50.")
    if mode == "local":
        return {"mode": "local"}
    if not cloud_consent:
        raise ValueError(
            "Authorize sending selected page content to Google before using Gemini."
        )
    config = configuration()
    if not config["configured"] or not config["model_valid"]:
        raise ValueError(
            "Configure GEMINI_API_KEY and a valid GEMINI_MODEL on the server, then restart. Local extraction is ready without a key."
        )
    return {
        "mode": mode,
        "scope": scope,
        "max_requests": max_requests,
        "model": config["model"],
        "cloud_consent": True,
    }


def run(path, workflow=None, ledger_path=None, save=None, **kwargs):
    workflow = workflow or {"mode": "local"}
    start = time.perf_counter()
    result = extract(path, **kwargs)
    result["workflow"] = workflow.copy()
    if workflow["mode"] == "local":
        return enrich(result)

    def emit(stage, message, **details):
        from datetime import datetime, timezone

        entry = {
            "at": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "message": message,
            **details,
        }
        result["events"].append(entry)
        kwargs.get("event", lambda *a: None)(entry)

    emit(
        "validate",
        "Local baseline complete. Selecting pages for optional Gemini assistance.",
    )
    with fitz.open(path) as source:
        doc = source if source.is_pdf else fitz.open("pdf", source.convert_to_pdf())
        try:
            try:
                result["gemini"] = assist(
                    result, doc, workflow, emit, ledger_path, save
                )
                result["issues"].extend(review_issues(result["gemini"]))
            except (GeminiError, OSError) as exc:
                message = (
                    str(exc)
                    if isinstance(exc, GeminiError)
                    else "Gemini ledger could not be saved; cloud assistance stopped. Local results retained."
                )
                result["gemini"] = {
                    "mode": "gemini",
                    "status": "unavailable",
                    "message": message,
                }
                result["issues"].append(
                    {
                        "kind": "gemini_coverage",
                        "severity": "warning",
                        "table": None,
                        "row": None,
                        "column": None,
                        "message": message,
                    }
                )
                emit("validate", message)
        finally:
            if doc is not source:
                doc.close()
    for i, issue in enumerate(result["issues"], 1):
        issue["id"] = i
    emit(
        "review",
        "Both workflows converge on source review and validated export; Gemini proposals do not overwrite data.",
    )
    result["elapsed_seconds"] = round(time.perf_counter() - start, 2)
    return enrich(result)
