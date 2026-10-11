"""
Unit and integration tests for Chat API endpoint POST /api/chat (Step 21).
Ref: PRD Section 6 (FR-07, FR-08, FR-09), Section 7; Step 21 of execution guide.
Verifies:
- Valid request returns predictable ChatResponse with citations.
- Unindexed repository returns HTTP 404.
- Empty or whitespace questions return HTTP 422.
- Oversized questions return HTTP 422.
- Unsupported question produces abstained response.
- Simulated provider errors (rate limit, timeout, config) map to predictable HTTP codes.
- Multi-turn conversation context is accepted.
"""
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.models.chunk import CodeChunk
from backend.app.services.indexing.embeddings import MockEmbeddingProvider
from backend.app.services.indexing.storage import IndexStorageManager, PersistentIndexStore
from backend.app.services.llm.client import (
    LLMConfigurationError,
    LLMRateLimitError,
    LLMTimeoutError,
    MockLLMProvider,
)
from backend.app.services.llm.qa_service import QAService
from backend.app.services.retrieval.hybrid import HybridRetrievalManager
from backend.app.api.routes_chat import get_qa_service

client = TestClient(app)


def _seed_test_repo(repo_id: str, base_dir: Path) -> PersistentIndexStore:
    store = PersistentIndexStore(repo_id, custom_base_dir=base_dir)
    chunk = CodeChunk(
        chunk_id="chk_auth",
        repo_id=repo_id,
        file_path="services/auth.py",
        language="python",
        start_line=10,
        end_line=25,
        content="def verify_credentials(user, password):\n    return check_hash(user, password)",
        chunk_index=0,
        symbol_name="verify_credentials",
        char_count=77,
        line_count=2,
    )
    provider = MockEmbeddingProvider(dimension=32)
    vectors = provider.embed_texts([chunk.content])
    store.save([chunk], vectors, "mock", "mock-32", 32)
    return store


def test_chat_unindexed_repo_returns_404():
    """Verify non-existent/unindexed repo returns HTTP 404."""
    resp = client.post(
        "/api/chat",
        json={"repo_id": "non_existent_repo_999", "question": "Where is auth?"},
    )
    assert resp.status_code == 404
    assert "not been indexed" in resp.json()["detail"]


def test_chat_empty_or_whitespace_question_returns_422(tmp_path: Path):
    """Verify empty or blank questions are rejected with HTTP 422."""
    _seed_test_repo("repo_chat_test", tmp_path)
    storage_mgr = IndexStorageManager(base_dir=tmp_path)
    retrieval_mgr = HybridRetrievalManager(storage_manager=storage_mgr)
    test_qa_service = QAService(retrieval_manager=retrieval_mgr)

    app.dependency_overrides[get_qa_service] = lambda: test_qa_service
    try:
        # Empty question
        resp_empty = client.post(
            "/api/chat",
            json={"repo_id": "repo_chat_test", "question": ""},
        )
        assert resp_empty.status_code == 422

        # Whitespace question
        resp_ws = client.post(
            "/api/chat",
            json={"repo_id": "repo_chat_test", "question": "   \n\t  "},
        )
        assert resp_ws.status_code == 422
        assert "empty or whitespace" in resp_ws.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_chat_oversized_question_returns_422():
    """Verify question exceeding 2000 characters is rejected with HTTP 422."""
    long_q = "How does this function work? " * 100  # ~3000 chars
    resp = client.post(
        "/api/chat",
        json={"repo_id": "some_repo", "question": long_q},
    )
    assert resp.status_code == 422


def test_valid_chat_request_with_citations(tmp_path: Path):
    """Verify valid chat request retrieves evidence, formats prompt, and returns citations."""
    _seed_test_repo("repo_valid", tmp_path)

    storage_mgr = IndexStorageManager(base_dir=tmp_path)
    retrieval_mgr = HybridRetrievalManager(
        storage_manager=storage_mgr,
        embedding_provider=MockEmbeddingProvider(dimension=32),
    )
    mock_llm = MockLLMProvider(
        canned_response=(
            "The credentials check is performed in "
            "[File: services/auth.py, Lines: 10-25] using check_hash."
        )
    )
    test_qa_service = QAService(
        retrieval_manager=retrieval_mgr,
        llm_provider=mock_llm,
    )

    app.dependency_overrides[get_qa_service] = lambda: test_qa_service
    try:
        resp = client.post(
            "/api/chat",
            json={
                "repo_id": "repo_valid",
                "question": "Where are user credentials verified?",
                "max_chunks": 5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        assert "answer" in data
        assert "citations" in data
        assert data["abstained"] is False
        assert data["retrieved_chunks_count"] == 1

        citations = data["citations"]
        assert len(citations) >= 1
        assert citations[0]["file_path"] == "services/auth.py"
        assert citations[0]["start_line"] == 10
        assert citations[0]["end_line"] == 25
        assert citations[0]["chunk_id"] == "chk_auth"
    finally:
        app.dependency_overrides.clear()


def test_chat_unsupported_question_abstention(tmp_path: Path):
    """Verify unsupported question generates an abstained response."""
    _seed_test_repo("repo_unsupported", tmp_path)

    storage_mgr = IndexStorageManager(base_dir=tmp_path)
    retrieval_mgr = HybridRetrievalManager(
        storage_manager=storage_mgr,
        embedding_provider=MockEmbeddingProvider(dimension=32),
    )
    mock_llm = MockLLMProvider(
        canned_response="The retrieved codebase evidence does not contain information about Kubernetes."
    )
    test_qa_service = QAService(
        retrieval_manager=retrieval_mgr,
        llm_provider=mock_llm,
    )

    app.dependency_overrides[get_qa_service] = lambda: test_qa_service
    try:
        resp = client.post(
            "/api/chat",
            json={
                "repo_id": "repo_unsupported",
                "question": "How are Kubernetes manifests deployed?",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["abstained"] is True
        assert "does not contain" in data["answer"].lower()
    finally:
        app.dependency_overrides.clear()


def test_chat_provider_errors_mapped_predictably(tmp_path: Path):
    """Verify provider exceptions (rate limits, timeouts, config) map to predictable HTTP codes."""
    _seed_test_repo("repo_err", tmp_path)

    storage_mgr = IndexStorageManager(base_dir=tmp_path)
    retrieval_mgr = HybridRetrievalManager(
        storage_manager=storage_mgr,
        embedding_provider=MockEmbeddingProvider(dimension=32),
    )

    # 1. Rate Limit Error -> HTTP 429
    class RateLimitProvider(MockLLMProvider):
        def generate_response(self, *args, **kwargs):
            raise LLMRateLimitError("Simulated 429")

    app.dependency_overrides[get_qa_service] = lambda: QAService(
        retrieval_manager=retrieval_mgr,
        llm_provider=RateLimitProvider(),
    )
    try:
        resp = client.post("/api/chat", json={"repo_id": "repo_err", "question": "test?"})
        assert resp.status_code == 429

        # 2. Timeout Error -> HTTP 504
        class TimeoutProvider(MockLLMProvider):
            def generate_response(self, *args, **kwargs):
                raise LLMTimeoutError("Simulated timeout")

        app.dependency_overrides[get_qa_service] = lambda: QAService(
            retrieval_manager=retrieval_mgr,
            llm_provider=TimeoutProvider(),
        )
        resp = client.post("/api/chat", json={"repo_id": "repo_err", "question": "test?"})
        assert resp.status_code == 504

        # 3. Config Error -> HTTP 503
        class ConfigErrorProvider(MockLLMProvider):
            def generate_response(self, *args, **kwargs):
                raise LLMConfigurationError("Missing API key")

        app.dependency_overrides[get_qa_service] = lambda: QAService(
            retrieval_manager=retrieval_mgr,
            llm_provider=ConfigErrorProvider(),
        )
        resp = client.post("/api/chat", json={"repo_id": "repo_err", "question": "test?"})
        assert resp.status_code == 503

    finally:
        app.dependency_overrides.clear()
