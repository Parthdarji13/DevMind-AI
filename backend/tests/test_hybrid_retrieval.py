"""
Unit tests for hybrid retrieval (Step 19).
Ref: PRD Section 6 (FR-06), Section 7; Step 19 of execution guide.
Verifies:
- Exact symbol name retrieval (BM25 advantage).
- Natural language conceptual retrieval (Vector advantage).
- Reciprocal Rank Fusion (RRF) and deduplication.
- Top-k and character context budgeting.
- Metadata filtering across hybrid pipelines.
- Graceful degradation when vector search is unavailable.
"""
from pathlib import Path
import pytest

from backend.app.models.chunk import CodeChunk
from backend.app.services.indexing.embeddings import (
    LocalSemanticEmbeddingProvider,
    MockEmbeddingProvider,
)
from backend.app.services.indexing.storage import PersistentIndexStore
from backend.app.services.retrieval.bm25 import BM25Index
from backend.app.services.retrieval.hybrid import (
    HybridRetrievalManager,
    HybridRetriever,
)
from backend.app.services.retrieval.vector import VectorSearchIndex


def _make_chunk(
    chunk_id: str,
    file_path: str,
    content: str,
    symbol_name: str = None,
    language: str = "python",
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
        symbol_name=symbol_name,
        char_count=len(content),
        line_count=len(lines),
    )


def test_exact_name_retrieval():
    """Verify exact identifier search brings exact-match chunk to the top."""
    c1 = _make_chunk(
        "chk_1",
        "services/auth.py",
        "def verify_jwt_signature(token: str) -> bool:\n    return check_secret(token)",
        symbol_name="verify_jwt_signature",
    )
    c2 = _make_chunk(
        "chk_2",
        "services/session.py",
        "def handle_user_session():\n    session = create_new_cookie()",
        symbol_name="handle_user_session",
    )

    bm25 = BM25Index([c1, c2])
    retriever = HybridRetriever(
        repo_id="test_repo",
        bm25_index=bm25,
        vector_index=None,  # pure lexical test
    )

    results = retriever.retrieve("verify_jwt_signature", top_k=2)
    assert len(results) > 0
    assert results[0].chunk_id == "chk_1"
    assert results[0].chunk.symbol_name == "verify_jwt_signature"
    assert results[0].retrieval_method == "lexical"


def test_natural_language_retrieval_and_rrf_fusion():
    """Verify natural-language semantic query retrieves relevant chunk and RRF fuses results."""
    provider = LocalSemanticEmbeddingProvider()

    c_auth = _make_chunk(
        "chk_auth",
        "services/security.py",
        "def validate_credentials(user, password):\n    salt = get_salt()\n    return bcrypt.verify(password, salt)",
        symbol_name="validate_credentials",
    )
    c_db = _make_chunk(
        "chk_db",
        "db/connection.py",
        "def init_postgres_pool():\n    return asyncpg.create_pool(dsn=DATABASE_URL)",
        symbol_name="init_postgres_pool",
    )
    c_cache = _make_chunk(
        "chk_cache",
        "cache/redis.py",
        "def invalidate_user_cache(user_id):\n    redis.delete(f'user:{user_id}')",
        symbol_name="invalidate_user_cache",
    )

    chunks = [c_auth, c_db, c_cache]
    vectors = provider.embed_texts([c.content for c in chunks])

    bm25 = BM25Index(chunks)
    vector_idx = VectorSearchIndex("test_repo", chunks, vectors, embedding_provider=provider)

    retriever = HybridRetriever(
        repo_id="test_repo",
        bm25_index=bm25,
        vector_index=vector_idx,
        rrf_k=60,
    )

    # Conceptual question matching security and credential validation
    results = retriever.retrieve("how to check user password and credentials?", top_k=3)
    assert len(results) > 0
    # Top result should be the auth chunk
    assert results[0].chunk_id == "chk_auth"
    assert results[0].chunk.file_path == "services/security.py"

    # Deduplication check: all chunk IDs must be strictly unique
    chunk_ids = [r.chunk_id for r in results]
    assert len(chunk_ids) == len(set(chunk_ids))


def test_top_k_and_context_budget_limiting():
    """Verify top_k limiting and character budget stopping condition."""
    chunks = [
        _make_chunk(f"chk_{i}", f"src/file_{i}.py", f"def func_{i}():\n    return {i} " * 10)
        for i in range(10)
    ]
    bm25 = BM25Index(chunks)
    retriever = HybridRetriever("test_repo", bm25, vector_index=None)

    # 1. Top-k limiting
    res_k = retriever.retrieve("func return", top_k=3)
    assert len(res_k) == 3

    # 2. Context character budget limit
    # Each chunk is ~170 chars; budget of 250 chars allows 1 chunk plus a second that gets capped
    res_budget = retriever.retrieve("func return", top_k=10, max_total_chars=250)
    total_chars = sum(r.chunk.char_count for r in res_budget)
    assert len(res_budget) <= 2
    assert total_chars >= 150


def test_metadata_filtering_in_hybrid_retrieval():
    """Verify filtering by language and path prefix in hybrid retrieval."""
    provider = MockEmbeddingProvider(dimension=32)

    c_py = _make_chunk("chk_py", "src/auth/token.py", "def generate_token(): pass", language="python")
    c_ts = _make_chunk("chk_ts", "src/auth/token.ts", "export function generateToken(): void {}", language="typescript")
    c_doc = _make_chunk("chk_doc", "docs/auth.md", "# Authentication Guide", language="markdown")

    chunks = [c_py, c_ts, c_doc]
    vectors = provider.embed_texts([c.content for c in chunks])

    bm25 = BM25Index(chunks)
    vector_idx = VectorSearchIndex("test_repo", chunks, vectors, embedding_provider=provider)
    retriever = HybridRetriever("test_repo", bm25, vector_idx)

    # Language filter
    py_only = retriever.retrieve("token", language="python")
    assert len(py_only) == 1
    assert py_only[0].chunk_id == "chk_py"

    # Path prefix filter
    docs_only = retriever.retrieve("auth", path_prefix="docs/")
    assert len(docs_only) == 1
    assert docs_only[0].chunk_id == "chk_doc"


def test_graceful_fallback_when_vector_search_fails():
    """Verify retriever falls back to BM25 when vector search has no provider or raises error."""
    c1 = _make_chunk("chk_1", "app/main.py", "def start_server(): print('running')")
    bm25 = BM25Index([c1])

    # Vector index initialized without embedding provider (would raise error if called directly)
    vector_idx = VectorSearchIndex("test_repo", [c1], [[0.1, 0.2]], embedding_provider=None)

    retriever = HybridRetriever("test_repo", bm25, vector_index=vector_idx)

    # Should not crash; gracefully fall back to BM25
    results = retriever.retrieve("start_server", top_k=5)
    assert len(results) == 1
    assert results[0].chunk_id == "chk_1"
    assert results[0].retrieval_method == "lexical"


def test_hybrid_manager_lifecycle(tmp_path: Path):
    """Verify HybridRetrievalManager correctly builds and caches retrievers from persistent storage."""
    provider = MockEmbeddingProvider(dimension=16)
    chunk = _make_chunk("chk_mgr", "utils.py", "def helper_func(): return True")

    store = PersistentIndexStore("repo_mgr", custom_base_dir=tmp_path)
    store.save([chunk], provider.embed_texts([chunk.content]), "mock", "mock-16", 16)

    from backend.app.services.indexing.storage import IndexStorageManager
    storage_mgr = IndexStorageManager(base_dir=tmp_path)
    retrieval_mgr = HybridRetrievalManager(storage_manager=storage_mgr, embedding_provider=provider)

    retriever = retrieval_mgr.get_retriever("repo_mgr")
    assert retriever.repo_id == "repo_mgr"
    assert retriever.vector_index is not None

    results = retrieval_mgr.retrieve("repo_mgr", "helper_func")
    assert len(results) == 1
    assert results[0].chunk_id == "chk_mgr"
