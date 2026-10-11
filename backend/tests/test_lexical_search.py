"""
Unit tests for BM25 lexical search (Step 17).
Verifies:
- Exact identifier and function name retrieval.
- Class and symbol name boosting.
- Sub-tokenization for camelCase and snake_case code identifiers.
- Filename matching bonus.
- Edge cases (empty queries, empty indices).
"""
import sys
from pathlib import Path
import pytest

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.chunk import CodeChunk
from app.services.retrieval.bm25 import (
    BM25Index,
    tokenize_code,
)


def make_chunk(cid: str, path: str, content: str, symbol: str = None) -> CodeChunk:
    return CodeChunk(
        chunk_id=cid,
        repo_id="test-repo",
        file_path=path,
        language="Python",
        start_line=1,
        end_line=len(content.split("\n")),
        content=content,
        chunk_index=0,
        symbol_name=symbol,
        line_count=len(content.split("\n")),
        char_count=len(content),
    )


def test_code_tokenizer():
    tokens = tokenize_code("getUserProfileByID(user_id: int)")
    # Should include original, snake_case subparts, and camelCase subparts
    assert "getuserprofilebyid" in tokens
    assert "get" in tokens
    assert "user" in tokens
    assert "profile" in tokens
    assert "id" in tokens
    assert "user_id" in tokens


def test_exact_function_name_retrieval():
    chunks = [
        make_chunk("chk_1", "src/auth.py", "def validate_jwt_token(token: str):\n    return decode(token)", "validate_jwt_token"),
        make_chunk("chk_2", "src/db.py", "def get_db_connection():\n    return create_engine(DATABASE_URL)", "get_db_connection"),
        make_chunk("chk_3", "src/ui.py", "def render_sidebar():\n    return HtmlNav()", "render_sidebar"),
    ]

    index = BM25Index(chunks)

    # Search for validate_jwt_token
    results = index.search("validate_jwt_token", top_k=3)
    assert len(results) > 0
    assert results[0].chunk_id == "chk_1"
    assert results[0].chunk.symbol_name == "validate_jwt_token"


def test_class_identifier_and_file_path_boost():
    chunks = [
        make_chunk("chk_db", "config/database.py", "class DatabaseConnectionPool:\n    def __init__(self, uri): self.uri = uri", "DatabaseConnectionPool"),
        make_chunk("chk_cache", "services/cache.py", "class RedisCacheManager:\n    def ping(self): pass", "RedisCacheManager"),
        make_chunk("chk_router", "api/routes.py", "def handle_home(): return 'OK'", "handle_home"),
    ]

    index = BM25Index(chunks)

    # Search explicitly mentioning class and file
    results = index.search("Where is DatabaseConnectionPool in database.py", top_k=2)
    assert len(results) > 0
    assert results[0].chunk_id == "chk_db"
    assert results[0].score > 0


def test_subtoken_snake_and_camel_matching():
    chunks = [
        make_chunk("chk_1", "src/payment.py", "const processStripeCheckout = async (cartItems) => { return charge(); }", "processStripeCheckout"),
        make_chunk("chk_2", "src/logger.py", "def log_system_event(event_name): pass", "log_system_event"),
    ]

    index = BM25Index(chunks)

    # Query with separate words: "stripe checkout"
    results = index.search("stripe checkout", top_k=1)
    assert len(results) == 1
    assert results[0].chunk_id == "chk_1"


def test_empty_query_and_empty_index():
    index = BM25Index([])
    assert index.search("hello") == []

    chunk = make_chunk("chk_1", "app.py", "print('hi')")
    index2 = BM25Index([chunk])
    assert index2.search("") == []
    assert index2.search("   ") == []
