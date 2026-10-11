"""
Unit tests for vector search and semantic retrieval.
Ref: PRD Section 6 (FR-06), Section 7; Step 18 of execution guide.
Verifies semantic fixtures, metadata filtering, repository isolation, and explicit failure modes.
"""
from pathlib import Path
import numpy as np
import pytest

from backend.app.models.chunk import CodeChunk
from backend.app.services.indexing.embeddings import (
    LocalSemanticEmbeddingProvider,
    MockEmbeddingProvider,
)
from backend.app.services.indexing.storage import PersistentIndexStore
from backend.app.services.retrieval.vector import (
    DimensionMismatchError,
    EmbeddingNotAvailableError,
    RepositoryNotIndexedError,
    VectorRetrievalError,
    VectorSearchIndex,
    VectorSearchManager,
)


def _make_chunk(
    chunk_id: str,
    file_path: str,
    content: str,
    language: str = "python",
    symbol: str = None,
    repo_id: str = "test_repo",
    chunk_index: int = 0,
) -> CodeChunk:
    lines = content.splitlines() or [""]
    return CodeChunk(
        chunk_id=chunk_id,
        repo_id=repo_id,
        file_path=file_path,
        language=language,
        start_line=1,
        end_line=len(lines),
        content=content,
        chunk_index=chunk_index,
        symbol_name=symbol,
        char_count=len(content),
        line_count=len(lines),
    )


def test_semantic_fixture_retrieves_relevant_chunk():
    """Verify semantic fixture: auth query returns auth chunk as top result."""
    provider = LocalSemanticEmbeddingProvider()

    auth_chunk = _make_chunk(
        chunk_id="chk_auth",
        file_path="services/auth.py",
        content="def authenticate_user(username: str, password_hash: str) -> bool:\n    verify_jwt_token(username)\n    return True",
        symbol="authenticate_user",
    )
    db_chunk = _make_chunk(
        chunk_id="chk_db",
        file_path="db/migrations.py",
        content="def apply_schema_migration(connection, version: int):\n    connection.execute('ALTER TABLE users ADD COLUMN updated_at')",
        symbol="apply_schema_migration",
    )
    billing_chunk = _make_chunk(
        chunk_id="chk_billing",
        file_path="billing/stripe.py",
        content="def charge_credit_card(amount: float, customer_id: str):\n    stripe.Charge.create(amount=amount, customer=customer_id)",
        symbol="charge_credit_card",
    )

    chunks = [auth_chunk, db_chunk, billing_chunk]
    texts = [c.content for c in chunks]
    vectors = provider.embed_texts(texts)

    index = VectorSearchIndex(
        repo_id="repo_test",
        chunks=chunks,
        vectors=vectors,
        embedding_provider=provider,
    )

    results = index.search("verify user authentication and JWT token", top_k=3)
    assert len(results) > 0
    assert results[0].chunk_id == "chk_auth"
    assert results[0].score > 0.0
    assert "services/auth.py" in results[0].chunk.file_path


def test_vector_search_metadata_filtering():
    """Verify filtering by file_path, path_prefix, and language."""
    provider = MockEmbeddingProvider(dimension=64)

    chunk_py1 = _make_chunk("chk_1", "src/auth/login.py", "def login(): pass", language="python")
    chunk_py2 = _make_chunk("chk_2", "src/db/repo.py", "def query_db(): pass", language="python")
    chunk_ts = _make_chunk("chk_3", "src/frontend/app.ts", "export function render(): void {}", language="typescript")

    chunks = [chunk_py1, chunk_py2, chunk_ts]
    vectors = provider.embed_texts([c.content for c in chunks])

    index = VectorSearchIndex("repo_filter", chunks, vectors, embedding_provider=provider)

    # Filter by exact language
    ts_results = index.search("render", language="typescript")
    assert len(ts_results) == 1
    assert ts_results[0].chunk_id == "chk_3"

    # Filter by path prefix
    auth_results = index.search("login", path_prefix="src/auth")
    assert len(auth_results) == 1
    assert auth_results[0].chunk_id == "chk_1"

    # Filter by exact file path
    db_results = index.search("query", file_path="src/db/repo.py")
    assert len(db_results) == 1
    assert db_results[0].chunk_id == "chk_2"

    # Filter with no matching files returns empty list
    none_results = index.search("login", file_path="nonexistent/file.py")
    assert none_results == []


def test_repository_isolation_via_store(tmp_path: Path):
    """Verify repository isolation: repo A vectors/chunks are never queried by repo B."""
    provider = MockEmbeddingProvider(dimension=32)

    chunk_a = _make_chunk("chk_a", "repo_a_file.py", "content for repository A")
    chunk_b = _make_chunk("chk_b", "repo_b_file.py", "content for repository B")

    # Persist repo A
    store_a = PersistentIndexStore("repo_a", custom_base_dir=tmp_path)
    store_a.save([chunk_a], provider.embed_texts([chunk_a.content]), "mock", "mock-32", 32)

    # Persist repo B
    store_b = PersistentIndexStore("repo_b", custom_base_dir=tmp_path)
    store_b.save([chunk_b], provider.embed_texts([chunk_b.content]), "mock", "mock-32", 32)

    # Search repo A
    index_a = VectorSearchIndex.from_store(store_a, embedding_provider=provider)
    res_a = index_a.search("repository", top_k=10)
    assert len(res_a) == 1
    assert res_a[0].chunk_id == "chk_a"
    assert all(r.chunk.file_path != "repo_b_file.py" for r in res_a)

    # Search repo B
    index_b = VectorSearchIndex.from_store(store_b, embedding_provider=provider)
    res_b = index_b.search("repository", top_k=10)
    assert len(res_b) == 1
    assert res_b[0].chunk_id == "chk_b"
    assert all(r.chunk.file_path != "repo_a_file.py" for r in res_b)


def test_explicit_error_unindexed_repository(tmp_path: Path):
    """Verify explicit RepositoryNotIndexedError when loading unindexed repo."""
    with pytest.raises(RepositoryNotIndexedError) as exc_info:
        VectorSearchIndex.from_repo_id("repo_missing_123", custom_base_dir=tmp_path)
    assert "not been indexed" in str(exc_info.value)


def test_explicit_error_dimension_mismatch():
    """Verify explicit DimensionMismatchError when query vector dimension differs."""
    chunk = _make_chunk("chk_1", "main.py", "def main(): pass")
    vectors = [[0.1, 0.2, 0.3]]  # 3 dimensions

    index = VectorSearchIndex("repo_dim", [chunk], vectors)
    wrong_dim_query = [0.1, 0.2, 0.3, 0.4, 0.5]  # 5 dimensions

    with pytest.raises(DimensionMismatchError) as exc_info:
        index.search_by_vector(wrong_dim_query)
    assert "Query vector dimension (5) does not match" in str(exc_info.value)


def test_explicit_error_missing_embedding_provider():
    """Verify explicit EmbeddingNotAvailableError if search() is called without provider."""
    chunk = _make_chunk("chk_1", "main.py", "def main(): pass")
    vectors = [[0.1, 0.2]]
    index = VectorSearchIndex("repo_no_provider", [chunk], vectors, embedding_provider=None)

    with pytest.raises(EmbeddingNotAvailableError) as exc_info:
        index.search("find main function")
    assert "No embedding provider configured" in str(exc_info.value)


def test_empty_query_and_empty_index_safety():
    """Verify graceful empty results on blank query or empty index."""
    provider = MockEmbeddingProvider(dimension=16)

    # Empty query string
    chunk = _make_chunk("chk_1", "main.py", "content")
    index = VectorSearchIndex("repo_empty_q", [chunk], provider.embed_texts(["content"]), provider)
    assert index.search("") == []
    assert index.search("   ") == []

    # Empty index
    empty_index = VectorSearchIndex("repo_empty_idx", [], [], provider)
    assert empty_index.search("anything") == []
    assert empty_index.search_by_vector([1.0] * 16) == []
