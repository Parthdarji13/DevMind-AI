"""
Unit tests for Public Git ingestion (Step 11).
Verifies controlled shallow clone, timeout handling, private/not-found repo handling,
and API integration (POST /api/ingest/git).
"""
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import pytest

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app
from app.services.ingestion.git_cloner import (
    clone_and_filter_public_repo,
    GitCloneError,
    GitTimeoutError,
)
from app.services.ingestion.repository_manager import repo_manager

client = TestClient(app)


def test_clone_and_filter_success_mock(tmp_path):
    # Simulate git clone placing files into target_dir
    target_dir = tmp_path / "cloned_repo"

    def fake_subprocess_run(cmd, capture_output, text, timeout, env, check):
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "app.py").write_text("print('hello')", encoding="utf-8")
        (target_dir / "README.md").write_text("# Cloned Repo", encoding="utf-8")
        (target_dir / ".git").mkdir()
        (target_dir / ".git" / "config").write_text("dummy", encoding="utf-8")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        val, report = clone_and_filter_public_repo(
            raw_url="https://github.com/example/sample-repo",
            target_dir=target_dir,
            resolve_dns=False,
        )

        assert val.is_valid is True
        assert val.repo_name == "sample-repo"
        assert report.total_included == 2
        assert "app.py" in report.included_files
        # Confirm .git was deleted
        assert not (target_dir / ".git").exists()


def test_clone_timeout_handling(tmp_path):
    target_dir = tmp_path / "timeout_repo"

    def fake_timeout(cmd, capture_output, text, timeout, env, check):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

    with patch("subprocess.run", side_effect=fake_timeout):
        with pytest.raises(GitTimeoutError) as exc_info:
            clone_and_filter_public_repo(
                raw_url="https://github.com/example/timeout-repo",
                target_dir=target_dir,
                resolve_dns=False,
            )
        assert "timed out" in str(exc_info.value).lower()
        # Verify temporary directory was cleaned up
        assert not target_dir.exists()


def test_clone_private_repo_rejected_cleanly(tmp_path):
    target_dir = tmp_path / "private_repo"

    def fake_auth_fail(cmd, capture_output, text, timeout, env, check):
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=128,
            stdout="",
            stderr="fatal: Authentication failed for 'https://github.com/secret/repo.git/'",
        )

    with patch("subprocess.run", side_effect=fake_auth_fail):
        with pytest.raises(GitCloneError) as exc_info:
            clone_and_filter_public_repo(
                raw_url="https://github.com/secret/repo",
                target_dir=target_dir,
                resolve_dns=False,
            )
        assert "private or requires authentication" in str(exc_info.value)
        assert not target_dir.exists()


def test_api_ingest_git_endpoint_success(tmp_path):
    def fake_subprocess_run(cmd, capture_output, text, timeout, env, check):
        # Extract target_dir from cmd args (last argument)
        dest_dir = Path(cmd[-1])
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / "index.ts").write_text("export const a = 1;", encoding="utf-8")
        (dest_dir / "README.md").write_text("# Title", encoding="utf-8")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_subprocess_run), \
         patch("app.services.ingestion.git_validator.validate_git_url") as mock_val:
        from app.services.ingestion.git_validator import GitValidationResult
        mock_val.return_value = GitValidationResult(
            is_valid=True,
            normalized_url="https://github.com/sample/test-repo.git",
            repo_name="test-repo",
            host="github.com",
        )

        response = client.post(
            "/api/ingest/git",
            json={"url": "https://github.com/sample/test-repo"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] in ("processing", "ready")

        assert data["source_type"] == "git"
        assert data["repo_name"] == "test-repo"
        assert data["stats"]["included_files"] == 2

        # Clean up
        repo_manager.cleanup_repository(data["repo_id"])


def test_api_ingest_git_endpoint_invalid_url():
    response = client.post(
        "/api/ingest/git",
        json={"url": "http://insecure-http.com/repo"},
    )
    assert response.status_code == 400
    assert "Invalid Git URL" in response.json()["detail"]
