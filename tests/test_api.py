import importlib
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGERLENS_DATA", str(tmp_path / "jobs"))
    import app.main as module

    module = importlib.reload(module)
    with TestClient(module.app) as client:
        yield client
    module.POOL.shutdown(wait=True)


def completed(client):
    response = client.post("/api/samples/01_invoice_register")
    assert response.status_code == 202
    job = response.json()["id"]
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        state = client.get("/api/jobs/" + job).json()
        if state["status"] in {"complete", "failed"}:
            break
        time.sleep(0.05)
    assert state["status"] == "complete"
    return job


def test_health_and_frontend(client):
    assert client.get("/api/health").json()["max_pages"] == 50
    assert "Less paperwork." in client.get("/").text
    assert client.get("/styles.css").status_code == 200
    assert client.get("/api/health").headers["X-Content-Type-Options"] == "nosniff"


def test_job_export_correct_delete_and_history(client):
    job = completed(client)
    assert len(client.get("/api/jobs").json()) == 1
    r = client.get(f"/api/jobs/{job}/result").json()
    assert r["row_count"] == 31
    patch = client.patch(
        f"/api/jobs/{job}/cells",
        json={"table": 1, "row": 1, "column": 8, "value": "999.00"},
    )
    assert patch.status_code == 200
    r = patch.json()
    assert r["edits"][0]["before"] == "44.00" and r["edits"][0]["after"] == "999.00"
    assert {"arithmetic", "total_mismatch"} <= {i["kind"] for i in r["issues"]}
    assert client.get(f"/api/jobs/{job}/export/xlsx").content[:2] == b"PK"
    assert client.get(f"/api/jobs/{job}/export/json").json()["edits"]
    assert client.get(f"/api/jobs/{job}/export/csv").status_code == 200
    assert client.get(f"/api/jobs/{job}/page/3").headers["content-type"] == "image/png"
    assert client.get(f"/api/jobs/{job}/page/4").status_code == 404
    assert client.delete("/api/jobs/" + job).status_code == 204
    assert client.get("/api/jobs/" + job).status_code == 404


@pytest.mark.parametrize(
    "name,data,status",
    [
        ("bad.txt", b"hello", 415),
        ("bad.pdf", b"%PDF-invalid", 422),
        ("large.pdf", b"0" * (40 * 1024 * 1024 + 1), 413),
    ],
    ids=["unsupported-type", "corrupt-pdf", "oversize-upload"],
)
def test_upload_rejections(client, name, data, status):
    assert client.post("/api/jobs", files={"file": (name, data)}).status_code == status


def test_path_and_origin_security(client):
    assert client.get("/api/jobs/not-a-uuid").status_code == 404
    assert (
        client.post(
            "/api/samples/01_invoice_register", headers={"origin": "https://evil.test"}
        ).status_code
        == 403
    )
    assert client.get("/api/health", headers={"host": "evil.test"}).status_code == 403
    assert client.post("/api/samples/no-such-file").status_code == 404


def test_invalid_cell_coordinates_rejected(client):
    job = completed(client)
    assert (
        client.patch(
            f"/api/jobs/{job}/cells",
            json={"table": 1, "row": 0, "column": 1, "value": "x"},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/jobs/{job}/cells",
            json={"table": 99, "row": 1, "column": 1, "value": "x"},
        ).status_code
        == 404
    )


def test_restart_marks_interrupted(client):
    import app.main as module

    job = "00000000-0000-0000-0000-000000000000"
    p = module.JOBS / job
    p.mkdir()
    module.save(
        p / "status.json", {"id": job, "status": "processing", "created": "2026-10-15"}
    )
    importlib.reload(module)
    assert module.load(p / "status.json")["status"] == "interrupted"
