"""
Unit and integration tests for multi-turn conversations (Step 23).
Ref: PRD Section 6 (FR-08), Section 7; Step 23 of execution guide.
Verifies:
- At least three consecutive questions work seamlessly without re-indexing or re-uploading.
- Follow-up questions resolve context and retrieve correct evidence without refresh.
- History bounding prevents prompt bloat.
- Repository isolation: sessions are strictly bound to a single repository.
"""
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.models.chat import ChatMessage, ChatRequest
from backend.app.models.chunk import CodeChunk
from backend.app.services.indexing.embeddings import MockEmbeddingProvider
from backend.app.services.indexing.storage import IndexStorageManager, PersistentIndexStore
from backend.app.services.llm.client import MockLLMProvider
from backend.app.services.llm.conversation import (
    ConversationManager,
    RepositoryContextMismatchError,
)
from backend.app.services.llm.qa_service import QAService
from backend.app.services.retrieval.hybrid import HybridRetrievalManager
from backend.app.api.routes_chat import get_qa_service

client = TestClient(app)


def _seed_test_repo(repo_id: str, base_dir: Path) -> PersistentIndexStore:
    store = PersistentIndexStore(repo_id, custom_base_dir=base_dir)
    chunks = [
        CodeChunk(
            chunk_id="chk_auth",
            repo_id=repo_id,
            file_path="services/auth.py",
            language="python",
            start_line=10,
            end_line=30,
            content=(
                "def authenticate_user(username: str, password_hash: str) -> bool:\n"
                "    if not verify_password(password_hash):\n"
                "        raise AuthenticationError('Invalid credentials')\n"
                "    return True"
            ),
            chunk_index=0,
            symbol_name="authenticate_user",
            char_count=165,
            line_count=4,
        ),
        CodeChunk(
            chunk_id="chk_db",
            repo_id=repo_id,
            file_path="db/models.py",
            language="python",
            start_line=1,
            end_line=20,
            content="class User:\n    id: int\n    username: str",
            chunk_index=0,
            symbol_name="User",
            char_count=42,
            line_count=3,
        ),
    ]
    provider = MockEmbeddingProvider(dimension=32)
    vectors = provider.embed_texts([c.content for c in chunks])
    store.save(chunks, vectors, "mock", "mock-32", 32)
    return store


def test_three_consecutive_questions_without_refresh(tmp_path: Path):
    """
    Acceptance test for Step 23:
    Verify at least three consecutive questions work in sequence on the same repository
    without re-upload or re-indexing, resolving follow-up context accurately.
    """
    _seed_test_repo("repo_multiturn", tmp_path)

    storage_mgr = IndexStorageManager(base_dir=tmp_path)
    retrieval_mgr = HybridRetrievalManager(
        storage_manager=storage_mgr,
        embedding_provider=MockEmbeddingProvider(dimension=32),
    )
    conv_mgr = ConversationManager(max_turns=6)

    # Dynamic mock LLM responding contextually
    class MultiTurnMockLLM(MockLLMProvider):
        def generate_response(self, system_prompt: str, user_prompt: str, *args, **kwargs) -> str:
            import re
            m = re.search(r"DEVELOPER QUESTION:\s*([^\n\r]+)", user_prompt)
            curr_q = m.group(1).lower() if m else user_prompt.lower()

            if "invalid" in curr_q or "error" in curr_q or "password" in curr_q:
                return (
                    "If credentials are invalid, it raises an AuthenticationError "
                    "[File: services/auth.py, Lines: 12-14]."
                )
            elif "parameter" in curr_q or "take" in curr_q:
                return (
                    "authenticate_user takes `username: str` and `password_hash: str` "
                    "as parameters [File: services/auth.py, Lines: 10-15]."
                )
            else:
                return (
                    "authenticate_user is defined in "
                    "[File: services/auth.py, Lines: 10-30]."
                )

    qa_service = QAService(
        retrieval_manager=retrieval_mgr,
        llm_provider=MultiTurnMockLLM(),
        conversation_manager=conv_mgr,
    )

    app.dependency_overrides[get_qa_service] = lambda: qa_service
    try:
        # Turn 1: Initial query
        resp1 = client.post(
            "/api/chat",
            json={
                "repo_id": "repo_multiturn",
                "question": "Where is authenticate_user defined?",
                "session_id": "session_test_123",
            },
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["session_id"] == "session_test_123"
        assert len(data1["citations"]) >= 1
        assert data1["citations"][0]["file_path"] == "services/auth.py"

        # Turn 2: Follow-up question using anaphoric reference ("it") without mentioning auth.py or function name
        resp2 = client.post(
            "/api/chat",
            json={
                "repo_id": "repo_multiturn",
                "question": "What parameters does it take?",
                "session_id": "session_test_123",
            },
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert "username" in data2["answer"]
        assert len(data2["citations"]) >= 1
        assert data2["citations"][0]["file_path"] == "services/auth.py"

        # Turn 3: Second follow-up question
        resp3 = client.post(
            "/api/chat",
            json={
                "repo_id": "repo_multiturn",
                "question": "How does it handle invalid passwords?",
                "session_id": "session_test_123",
            },
        )
        assert resp3.status_code == 200
        data3 = resp3.json()
        assert "AuthenticationError" in data3["answer"]
        assert len(data3["citations"]) >= 1
        assert data3["citations"][0]["file_path"] == "services/auth.py"

        # Verify all 3 turns were stored in session
        _, history = conv_mgr.get_or_create_session("session_test_123", "repo_multiturn")
        assert len(history) == 6  # 3 pairs of user + assistant messages

    finally:
        app.dependency_overrides.clear()


def test_conversation_history_bounding():
    """Verify ConversationManager bounds history to max_turns and max_history_chars."""
    conv_mgr = ConversationManager(max_turns=3, max_history_chars=500)

    # Generate 10 turns (20 messages)
    history: list[ChatMessage] = []
    for i in range(10):
        history.append(ChatMessage(role="user", content=f"Question {i} about code"))
        history.append(ChatMessage(role="assistant", content=f"Answer {i} referencing files"))

    bounded = conv_mgr.sanitize_and_bound_history(history)

    # Must be bounded to at most max_turns * 2 = 6 messages
    assert len(bounded) <= 6
    # Most recent message must be preserved
    assert bounded[-1].content == "Answer 9 referencing files"
    # Total character length must not exceed budget
    total_chars = sum(len(m.content) for m in bounded)
    assert total_chars <= 500


def test_repository_isolation_across_sessions():
    """Verify that a session cannot be reused across different repositories."""
    conv_mgr = ConversationManager()

    # Create session bound to repo_a
    sess_id, _ = conv_mgr.get_or_create_session("sess_alpha", "repo_alpha")
    assert sess_id == "sess_alpha"

    # Attempting to use the same session_id for repo_beta must raise RepositoryContextMismatchError
    with pytest.raises(RepositoryContextMismatchError) as exc_info:
        conv_mgr.get_or_create_session("sess_alpha", "repo_beta")
    assert "bound to repository 'repo_alpha'" in str(exc_info.value)


def test_anaphoric_query_contextualization():
    """Verify follow-up query contextualizer enriches anaphoric questions with anchor symbols."""
    conv_mgr = ConversationManager()
    history = [
        ChatMessage(role="user", content="Where is the authenticate_user handler located?"),
        ChatMessage(role="assistant", content="In services/auth.py"),
    ]

    # Short follow-up using "it"
    follow_up = "What does it return?"
    contextualized = conv_mgr.contextualize_query(follow_up, history)

    # Must be anchored with authenticate_user
    assert "authenticate_user" in contextualized
    assert "What does it return?" in contextualized

    # Standalone non-anaphoric query should remain untouched
    standalone = "Explain the database migration flow"
    assert conv_mgr.contextualize_query(standalone, history) == standalone
