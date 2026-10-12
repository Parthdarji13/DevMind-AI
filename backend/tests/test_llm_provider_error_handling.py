"""
Unit tests for LLM provider error handling and zero-secret policy (Step 24).
Ref: PRD Section 7, Section 8, Section 9; Step 24 of execution guide.
Verifies:
- Missing, empty, or placeholder keys raise LLMConfigurationError.
- Secrets, tokens, and query parameter keys are strictly masked by sanitize_error_text.
- Rate limits (HTTP 429) raise LLMRateLimitError and return HTTP 429.
- Timeouts raise LLMTimeoutError and return HTTP 504.
- External server failures (HTTP 500/503) raise LLMAPIError and return HTTP 502.
- Malformed provider outputs are handled safely without unhandled crashes or stack traces.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import httpx
import pytest

from backend.app.main import app
from backend.app.services.indexing.embeddings import MockEmbeddingProvider
from backend.app.services.indexing.storage import IndexStorageManager, PersistentIndexStore
from backend.app.models.chunk import CodeChunk
from backend.app.services.llm.client import (
    GeminiLLMProvider,
    GroqLLMProvider,
    LLMAPIError,
    LLMConfigurationError,
    LLMRateLimitError,
    LLMTimeoutError,
    OpenAILLMProvider,
    sanitize_error_text,
)
from backend.app.services.llm.qa_service import QAService
from backend.app.services.retrieval.hybrid import HybridRetrievalManager
from backend.app.api.routes_chat import get_qa_service

client = TestClient(app)


def test_missing_or_placeholder_keys_raise_config_error():
    """Verify that empty or placeholder API keys fail immediately with clear configuration error."""
    # Gemini
    with pytest.raises(LLMConfigurationError) as exc_gemini:
        GeminiLLMProvider(api_key="")
    assert "GEMINI_API_KEY is not configured" in str(exc_gemini.value)

    with pytest.raises(LLMConfigurationError):
        GeminiLLMProvider(api_key="your_gemini_api_key_here")

    # OpenAI
    with pytest.raises(LLMConfigurationError) as exc_openai:
        OpenAILLMProvider(api_key="")
    assert "OPENAI_API_KEY is not configured" in str(exc_openai.value)

    with pytest.raises(LLMConfigurationError):
        OpenAILLMProvider(api_key="your_openai_api_key_here")

    # Groq
    with pytest.raises(LLMConfigurationError) as exc_groq:
        GroqLLMProvider(api_key="")
    assert "GROQ_API_KEY is not configured" in str(exc_groq.value)


def test_zero_secret_leak_sanitization():
    """Verify sanitize_error_text strictly masks API keys, bearer tokens, and credentials."""
    # Query parameter key
    dirty_url = "https://generativelanguage.googleapis.com/v1beta/models?key=AIzaSySecret123456789"
    sanitized = sanitize_error_text(dirty_url)
    assert "AIzaSySecret123456789" not in sanitized
    assert "key=***" in sanitized

    # Bearer token
    dirty_auth = "Authorization: Bearer sk-proj-supersecrettoken987654321"
    sanitized_auth = sanitize_error_text(dirty_auth)
    assert "sk-proj-supersecrettoken987654321" not in sanitized_auth
    assert "Bearer ***" in sanitized_auth

    # Header representation
    dirty_header = 'x-goog-api-key: "AIzaSyTopSecret"'
    sanitized_header = sanitize_error_text(dirty_header)
    assert "AIzaSyTopSecret" not in sanitized_header
    assert "x-goog-api-key" in sanitized_header
    assert "***" in sanitized_header


def test_gemini_rate_limit_and_timeout_simulation():
    """Verify simulated HTTP 429 and timeouts from Gemini raise correct error types."""
    provider = GeminiLLMProvider(api_key="valid_dummy_key", timeout=1.0)

    # 1. Simulate 429 Rate Limit
    mock_resp_429 = MagicMock(status_code=429, text="Rate limit exceeded")
    with patch("httpx.Client.post", return_value=mock_resp_429):
        with pytest.raises(LLMRateLimitError) as exc_info:
            provider.generate_response("system", "user")
        assert "rate limit exceeded" in str(exc_info.value).lower()

    # 2. Simulate Timeout
    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Read timed out")):
        with pytest.raises(LLMTimeoutError) as exc_info:
            provider.generate_response("system", "user")
        assert "timed out" in str(exc_info.value).lower()


def test_openai_server_error_and_malformed_json_simulation():
    """Verify OpenAI 500 error and malformed output handling."""
    provider = OpenAILLMProvider(api_key="valid_dummy_key", timeout=1.0)

    # 1. Simulate 500 External Server Error
    mock_resp_500 = MagicMock(status_code=500, text="Internal Server Error")
    with patch("httpx.Client.post", return_value=mock_resp_500):
        with pytest.raises(LLMAPIError) as exc_info:
            provider.generate_response("system", "user")
        assert "HTTP 500" in str(exc_info.value)

    # 2. Simulate Malformed JSON
    mock_resp_bad_json = MagicMock(status_code=200)
    mock_resp_bad_json.json.side_effect = ValueError("Invalid JSON")
    with patch("httpx.Client.post", return_value=mock_resp_bad_json):
        with pytest.raises(LLMAPIError) as exc_info:
            provider.generate_response("system", "user")
        assert "Failed to parse OpenAI response" in str(exc_info.value)


def test_end_to_end_recoverable_error_responses(tmp_path: Path):
    """Verify simulated failures produce clean JSON error responses without stack traces."""
    # Seed isolated repository
    store = PersistentIndexStore("repo_fail_test", custom_base_dir=tmp_path)
    chunk = CodeChunk(
        chunk_id="chk_1",
        repo_id="repo_fail_test",
        file_path="main.py",
        language="python",
        start_line=1,
        end_line=5,
        content="def main(): pass",
        chunk_index=0,
        char_count=16,
        line_count=1,
    )
    provider = MockEmbeddingProvider(dimension=16)
    store.save([chunk], provider.embed_texts([chunk.content]), "mock", "mock-16", 16)

    storage_mgr = IndexStorageManager(base_dir=tmp_path)
    retrieval_mgr = HybridRetrievalManager(storage_manager=storage_mgr, embedding_provider=provider)

    # Test error cases with custom mock LLM throwing specific provider errors
    class CrashingProvider(GeminiLLMProvider):
        def __init__(self, error_to_raise):
            self.error_to_raise = error_to_raise
        def generate_response(self, *args, **kwargs):
            raise self.error_to_raise

    test_cases = [
        (LLMRateLimitError("Quota exceeded"), 429),
        (LLMTimeoutError("Request timed out"), 504),
        (LLMConfigurationError("Invalid key"), 503),
        (LLMAPIError("Gateway failure"), 502),
    ]

    for err_instance, expected_status in test_cases:
        qa_service = QAService(
            retrieval_manager=retrieval_mgr,
            llm_provider=CrashingProvider(err_instance),
        )
        app.dependency_overrides[get_qa_service] = lambda: qa_service
        try:
            resp = client.post(
                "/api/chat",
                json={"repo_id": "repo_fail_test", "question": "Where is main?"},
            )
            assert resp.status_code == expected_status
            body = resp.json()
            assert "detail" in body
            # Crucial zero-leak check: stack trace must NEVER be in response detail
            assert "Traceback (most recent call last)" not in body["detail"]
            assert len(body["detail"]) > 0
        finally:
            app.dependency_overrides.pop(get_qa_service, None)
