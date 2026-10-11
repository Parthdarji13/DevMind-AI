"""
Unit tests for Ingestion Summary and Progress Tracking (Step 12).
Verifies:
- 5-stage progress lifecycle matching PRD Section 17.5.
- Real, non-faked percentage calculations.
- Strict mathematical counter reconciliation (discovered == included + skipped).
- API endpoint GET /api/ingest/progress/{repo_id}.
"""
import io
import sys
import zipfile
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app
from app.models.repository import (
    SourceType,
    StageStatus,
    RepositoryStatus,
)
from app.services.ingestion.progress_tracker import ProgressTracker
from app.services.ingestion.repository_manager import repo_manager

client = TestClient(app)


def test_progress_initialization():
    prog = ProgressTracker.initialize_progress("test-123", "my-repo", SourceType.ZIP)
    assert prog.repo_id == "test-123"
    assert prog.current_step == 1
    assert prog.percentage == 0
    assert len(prog.stages) == 5
    assert prog.stages[0].name == "Fetched repository"
    assert prog.stages[0].status == StageStatus.IN_PROGRESS
    assert prog.stages[1].status == StageStatus.WAITING


def test_progress_advancement_and_percentage():
    prog = ProgressTracker.initialize_progress("test-123", "my-repo", SourceType.ZIP)

    # Complete Step 1 -> 20%
    ProgressTracker.complete_stage(prog, 1, "Fetched archive successfully")
    assert prog.stages[0].status == StageStatus.DONE
    assert prog.percentage == 20
    assert prog.current_step == 2
    assert prog.stages[1].status == StageStatus.IN_PROGRESS

    # Complete Step 2 -> 40%
    ProgressTracker.complete_stage(prog, 2, "Filtered files")
    assert prog.percentage == 40
    assert prog.current_step == 3

    # In-progress Step 3 with 50 of 100 files -> 40% + 10% = 50%
    ProgressTracker.advance_to_stage(
        prog,
        step_number=3,
        status=StageStatus.IN_PROGRESS,
        detail="Chunking files",
        current_count=50,
        total_count=100,
    )
    assert prog.percentage == 50

    # Advance to Stage 5 done -> 100% and READY
    for step in range(3, 6):
        ProgressTracker.complete_stage(prog, step, f"Step {step} done")
    assert prog.percentage == 100
    assert prog.overall_status == RepositoryStatus.READY


def test_counter_reconciliation_integrity():
    prog = ProgressTracker.initialize_progress("test-123", "my-repo", SourceType.ZIP)

    # Valid: 10 discovered = 7 included + 3 skipped
    valid = ProgressTracker.set_metrics(
        prog,
        discovered=10,
        included=7,
        skipped=3,
        failed=0,
        indexed=7,
        skipped_breakdown={"secret": 1, "dependency": 2},
    )
    assert valid is True
    assert prog.reconcile_counters() is True

    # Invalid: 10 discovered != 5 included + 3 skipped (discrepancy of 2)
    valid_bad = ProgressTracker.set_metrics(
        prog,
        discovered=10,
        included=5,
        skipped=3,
    )
    assert valid_bad is False
    assert prog.reconcile_counters() is False


def test_api_progress_endpoint_on_live_upload():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("app.py", "print('hello')")
        zf.writestr("test.py", "assert True")
        zf.writestr(".env", "SECRET=123")
    buf.seek(0)

    # Upload
    upload_res = client.post(
        "/api/ingest/zip",
        files={"file": ("project.zip", buf, "application/zip")},
    )
    assert upload_res.status_code == 201
    repo_id = upload_res.json()["repo_id"]

    # Query progress endpoint
    prog_res = client.get(f"/api/ingest/progress/{repo_id}")
    assert prog_res.status_code == 200
    prog_data = prog_res.json()

    assert prog_data["repo_id"] == repo_id
    assert prog_data["metrics"]["discovered_files"] == 3
    assert prog_data["metrics"]["included_files"] == 2
    assert prog_data["metrics"]["skipped_files"] == 1
    # Check that discovered == included + skipped
    assert prog_data["metrics"]["discovered_files"] == (
        prog_data["metrics"]["included_files"] + prog_data["metrics"]["skipped_files"]
    )
    assert prog_data["skipped_breakdown"]["secret"] == 1
    assert "Python" in prog_data["languages"]

    # Clean up
    repo_manager.cleanup_repository(repo_id)
