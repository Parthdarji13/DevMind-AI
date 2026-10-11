"""
Unit tests for the end-to-end repository indexing pipeline (Step 26).
Verifies:
- Execution of Stage 3 (Chunking) and Stage 4 (Indexing/Embedding) through Stage 5 (Ready).
- Strict non-faked counter reconciliation.
- Disk persistence in PersistentIndexStore.
- Failure handling when repository directory is missing or empty.
"""
import sys
from pathlib import Path
import pytest

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.repository import RepositoryStatus, StageStatus, SourceType
from app.services.ingestion.repository_manager import repo_manager
from app.services.indexing.pipeline import run_repository_indexing
from app.services.indexing.storage import PersistentIndexStore


def test_indexing_pipeline_success(tmp_path):
    # 1. Create a repository record
    repo = repo_manager.create_repository(name="sample-pipeline-repo", source_type=SourceType.GIT)
    repo_dir = repo_manager.get_repo_dir(repo.repo_id)
    repo_dir.mkdir(parents=True, exist_ok=True)

    # 2. Write sample files
    (repo_dir / "main.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    (repo_dir / "utils.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (repo_dir / "notes.txt").write_text("Repository documentation file.\n", encoding="utf-8")

    # 3. Execute indexing pipeline
    success = run_repository_indexing(repo.repo_id)
    assert success is True

    # 4. Verify progress and stages
    progress = repo.progress
    assert progress is not None
    assert progress.percentage == 100
    assert progress.overall_status == RepositoryStatus.READY
    assert len(progress.stages) == 5

    for stage in progress.stages:
        assert stage.status == StageStatus.DONE

    # 5. Verify metrics and reconciliation
    assert progress.metrics.included_files == 3
    assert progress.metrics.indexed_files == 3
    assert progress.reconcile_counters() is True

    # 6. Verify disk persistence
    store = PersistentIndexStore(repo_id=repo.repo_id)
    assert store.exists() is True
    chunks = store.get_chunks()
    assert len(chunks) >= 3

    # Clean up
    repo_manager.cleanup_repository(repo.repo_id)
    store.clear()


def test_indexing_pipeline_empty_repo_fails_gracefully():
    repo = repo_manager.create_repository(name="empty-repo", source_type=SourceType.ZIP)
    repo_dir = repo_manager.get_repo_dir(repo.repo_id)
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Repo dir is empty (0 source files)
    success = run_repository_indexing(repo.repo_id)
    assert success is False

    assert repo.status == RepositoryStatus.FAILED
    assert repo.progress.overall_status == RepositoryStatus.FAILED
    assert "No supported source code files" in repo.progress.error_message

    repo_manager.cleanup_repository(repo.repo_id)
