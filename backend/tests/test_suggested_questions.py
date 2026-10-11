"""
Unit and integration tests for repository-derived suggested questions (Step 29).
Ref: Step 29 of execution guide; PRD Section 6 (FR-07).
Verifies:
- Suggestions are derived from real indexed files and symbols.
- Every suggestion identifies `derived_from` source file/symbol.
- Every suggestion has `is_verified == False` (exploratory, not pre-verified).
- API endpoint GET /api/chat/suggested-questions/{repo_id} behaves correctly:
  - 404 for unindexed repository.
  - 200 with structured suggestions for indexed repository.
"""
from pathlib import Path
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.models.chunk import CodeChunk
from backend.app.services.indexing.storage import PersistentIndexStore
from backend.app.services.llm.suggestions import SuggestionService

client = TestClient(app)


def test_suggestion_service_derives_from_files_and_symbols(tmp_path: Path):
    """Verify SuggestionService derives categorized questions tied to real files and symbols."""
    repo_id = "test-suggestions-repo"
    store = PersistentIndexStore(repo_id, custom_base_dir=tmp_path)

    chunks = [
        CodeChunk(
            chunk_id="c1",
            repo_id=repo_id,
            file_path="src/main.py",
            start_line=1,
            end_line=25,
            content="def initialize_app():\n    pass",
            symbol_name="initialize_app",
            language="python",
            chunk_index=0,
            line_count=25,
            char_count=32,
        ),
        CodeChunk(
            chunk_id="c2",
            repo_id=repo_id,
            file_path="src/api/routes.py",
            start_line=1,
            end_line=30,
            content="@router.get('/items')\ndef get_items():\n    return []",
            symbol_name="get_items",
            language="python",
            chunk_index=0,
            line_count=30,
            char_count=52,
        ),
        CodeChunk(
            chunk_id="c3",
            repo_id=repo_id,
            file_path="src/models/user.py",
            start_line=1,
            end_line=40,
            content="class UserProfile(BaseModel):\n    id: int",
            symbol_name="UserProfile",
            language="python",
            chunk_index=0,
            line_count=40,
            char_count=42,
        ),
        CodeChunk(
            chunk_id="c4",
            repo_id=repo_id,
            file_path="src/auth/jwt_guard.py",
            start_line=1,
            end_line=35,
            content="def verify_token(token: str):\n    pass",
            symbol_name="verify_token",
            language="python",
            chunk_index=0,
            line_count=35,
            char_count=39,
        ),
    ]

    vectors = [[0.1, 0.2, 0.3, 0.4] for _ in range(len(chunks))]
    store.save(chunks, vectors, provider_name="mock", model_name="mock-model", dimension=4)

    mock_manager = MagicMock()
    mock_manager.get_store.return_value = store

    service = SuggestionService(storage_manager=mock_manager)
    res = service.generate_suggestions(repo_id)

    assert res.repo_id == repo_id
    assert res.total_chunks_analyzed == 4
    assert len(res.suggestions) >= 4

    categories = [s.category for s in res.suggestions]
    assert "Architecture" in categories
    assert "API & Routing" in categories
    assert "Data & Models" in categories
    assert "Security & Auth" in categories

    for s in res.suggestions:
        # Step 29 requirement: suggestions must not claim to be pre-verified
        assert s.is_verified is False
        # Must specify where it was derived from
        assert any(f in s.derived_from for f in ("src/main.py", "src/api/routes.py", "src/models/user.py", "src/auth/jwt_guard.py"))
        assert len(s.question) > 10


def test_suggestions_unindexed_repo_returns_404():
    """Verify endpoint returns 404 when requested repository index does not exist."""
    res = client.get("/api/chat/suggested-questions/nonexistent-repo-99999")
    assert res.status_code == 404
    data = res.json()
    assert "not been indexed yet" in data["detail"]


def test_suggestions_empty_repo_id_returns_404_or_400():
    """Verify endpoint rejects empty or whitespace repo id."""
    res = client.get("/api/chat/suggested-questions/%20%20%20")
    assert res.status_code in (400, 404)


def test_suggestions_with_real_indexed_store(tmp_path: Path, monkeypatch):
    """Integration test verifying GET endpoint returns valid suggestions for indexed store."""
    repo_id = "integration-suggest-repo"
    store = PersistentIndexStore(repo_id, custom_base_dir=tmp_path)

    chunks = [
        CodeChunk(
            chunk_id="chunk_1",
            repo_id=repo_id,
            file_path="package.json",
            start_line=1,
            end_line=20,
            content='{"name": "my-app", "version": "1.0.0"}',
            symbol_name=None,
            language="json",
            chunk_index=0,
            line_count=20,
            char_count=39,
        ),
        CodeChunk(
            chunk_id="chunk_2",
            repo_id=repo_id,
            file_path="src/controllers/paymentController.ts",
            start_line=1,
            end_line=50,
            content="export function processPayment() {}",
            symbol_name="processPayment",
            language="typescript",
            chunk_index=0,
            line_count=50,
            char_count=35,
        ),
    ]

    vectors = [[0.1, 0.2, 0.3, 0.4] for _ in range(len(chunks))]
    store.save(chunks, vectors, provider_name="mock", model_name="mock-model", dimension=4)

    # Monkeypatch settings to point to tmp_path
    from backend.app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "indices_dir", tmp_path)

    # Also monkeypatch PersistentIndexStore default base
    import backend.app.services.indexing.storage as storage_mod
    monkeypatch.setattr(storage_mod.settings, "indices_dir", tmp_path)

    res = client.get(f"/api/chat/suggested-questions/{repo_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["repo_id"] == repo_id
    assert len(data["suggestions"]) >= 2

    # Verify fields
    for item in data["suggestions"]:
        assert "question" in item
        assert "category" in item
        assert "derived_from" in item
        assert item["is_verified"] is False
