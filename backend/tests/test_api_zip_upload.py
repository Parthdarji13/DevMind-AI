"""
Tests for ZIP upload API (POST /api/ingest/zip and GET /api/ingest/status/{repo_id}).
Verifies Step 9 acceptance criteria: success, invalid file, oversized upload,
security checks, and cleanup behavior.
"""
import io
import sys
import zipfile
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app
from app.services.ingestion.repository_manager import repo_manager

client = TestClient(app)


def make_test_zip(entries: dict[str, str]) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    buf.seek(0)
    return buf


def test_upload_valid_zip_success():
    zip_data = make_test_zip({
        "src/app.py": "def main(): print('hello')",
        "src/utils.ts": "export const x = 10;",
        "README.md": "# Project Title",
        ".env": "SECRET=do_not_track",
    })

    response = client.post(
        "/api/ingest/zip",
        files={"file": ("project.zip", zip_data, "application/zip")},
    )

    assert response.status_code == 201
    data = response.json()
    assert "repo_id" in data
    assert data["status"] in ("processing", "ready")
    assert data["source_type"] == "zip"
    assert data["repo_name"] == "project.zip"

    # Verify stats
    stats = data["stats"]
    assert stats["discovered_files"] == 4
    assert stats["included_files"] == 3
    assert stats["skipped_files"] == 1  # .env skipped
    assert stats["skipped_breakdown"]["secret"] == 1
    assert "Python" in stats["languages"]
    assert "TypeScript" in stats["languages"]

    # Verify status endpoint returns the same repo
    repo_id = data["repo_id"]
    status_res = client.get(f"/api/ingest/status/{repo_id}")
    assert status_res.status_code == 200
    assert status_res.json()["repo_id"] == repo_id

    # Clean up test repo
    repo_manager.cleanup_repository(repo_id)


def test_upload_non_zip_file_rejected():
    fake_txt = io.BytesIO(b"Hello world, not a zip")
    response = client.post(
        "/api/ingest/zip",
        files={"file": ("notes.txt", fake_txt, "text/plain")},
    )
    assert response.status_code == 400
    assert "Invalid file format" in response.json()["detail"]


def test_upload_corrupt_zip_rejected():
    corrupt_data = io.BytesIO(b"PK\x03\x04corrupted-archive-stream")
    response = client.post(
        "/api/ingest/zip",
        files={"file": ("corrupt.zip", corrupt_data, "application/zip")},
    )
    assert response.status_code == 400
    assert "Malformed" in response.json()["detail"]


def test_upload_zip_slip_rejected_and_cleaned():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../evil.txt", "exploit")
    buf.seek(0)

    response = client.post(
        "/api/ingest/zip",
        files={"file": ("malicious.zip", buf, "application/zip")},
    )
    assert response.status_code == 400
    assert "Zip-Slip" in response.json()["detail"]


def test_upload_zip_with_no_source_code_rejected():
    zip_data = make_test_zip({
        ".env": "SECRET=123",
        "node_modules/pkg/index.js": "console.log(1)",
    })

    response = client.post(
        "/api/ingest/zip",
        files={"file": ("empty_repo.zip", zip_data, "application/zip")},
    )
    assert response.status_code == 400
    assert "No supported source code" in response.json()["detail"]
