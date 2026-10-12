"""
Unit tests for Embeddings service (Step 15).
Verifies:
- Consistent dimensionality.
- L2 unit vector normalization for cosine dot-product.
- Safe batching of inputs.
- Relative semantic similarity on code terms.
- Strict rejection of missing/placeholder credentials without faking semantic capability.
"""
import math
import sys
from pathlib import Path
import pytest

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.indexing.embeddings import (
    LocalSemanticEmbeddingProvider,
    LocalHashEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    FastEmbedEmbeddingProvider,
    MockEmbeddingProvider,
    GeminiEmbeddingProvider,
    OpenAIEmbeddingProvider,
    EmbeddingConfigurationError,
    get_embedding_provider,
)


def test_local_provider_dimension_and_normalization():
    provider = LocalSemanticEmbeddingProvider(dimension=384)
    assert provider.dimension == 384

    texts = [
        "def connect_db(url: str): return create_engine(url)",
        "async function fetchUserData(id) { return api.get(`/users/${id}`); }",
        "",  # Empty string edge case
    ]

    vectors = provider.embed_texts(texts)
    assert len(vectors) == 3

    for vec in vectors:
        assert len(vec) == 384
        # Verify L2 unit norm (sum of squares == 1.0)
        norm_sq = sum(x * x for x in vec)
        assert math.isclose(norm_sq, 1.0, rel_tol=1e-3)


def test_safe_batching_order_preserved():
    provider = LocalSemanticEmbeddingProvider(dimension=384)
    # 45 sample snippets
    texts = [f"const variable_{i} = {i * 10};" for i in range(45)]

    # Batch in small chunks of 10
    vectors = provider.embed_texts(texts, batch_size=10)
    assert len(vectors) == 45

    # Verify query embedding matches individual embedding
    single = provider.embed_query(texts[0])
    assert single == vectors[0]


def test_semantic_similarity_relative_rank():
    provider = LocalSemanticEmbeddingProvider(dimension=384)

    vec_db1 = provider.embed_query("postgresql database connection pool configured in settings")
    vec_db2 = provider.embed_query("database connect error timeout connecting to db")
    vec_ui = provider.embed_query("render navigation bar button click style css header")

    # Cosine similarity is dot product of normalized vectors
    sim_related = sum(a * b for a, b in zip(vec_db1, vec_db2))
    sim_unrelated = sum(a * b for a, b in zip(vec_db1, vec_ui))

    # Semantically related code texts should score higher similarity than unrelated UI text
    assert sim_related > sim_unrelated


def test_missing_credentials_fails_explicitly():
    # Gemini requires non-placeholder key
    with pytest.raises(EmbeddingConfigurationError):
        GeminiEmbeddingProvider(api_key="")

    with pytest.raises(EmbeddingConfigurationError):
        GeminiEmbeddingProvider(api_key="your_gemini_api_key_here")

    # OpenAI requires non-placeholder key
    with pytest.raises(EmbeddingConfigurationError):
        OpenAIEmbeddingProvider(api_key="")

    with pytest.raises(EmbeddingConfigurationError):
        OpenAIEmbeddingProvider(api_key="your_openai_api_key_here")


def test_factory_creation():
    local_p = get_embedding_provider("local")
    assert isinstance(local_p, (LocalSemanticEmbeddingProvider, SentenceTransformerEmbeddingProvider, FastEmbedEmbeddingProvider))

    fast_p = get_embedding_provider("fastembed")
    assert isinstance(fast_p, FastEmbedEmbeddingProvider)

    local_hash_p = get_embedding_provider("local_hash")
    assert isinstance(local_hash_p, LocalHashEmbeddingProvider)

    mock_p = get_embedding_provider("mock")
    assert isinstance(mock_p, MockEmbeddingProvider)

    with pytest.raises(EmbeddingConfigurationError):
        get_embedding_provider("unsupported_provider_xyz")


def test_sentence_transformer_error_handling_when_not_installed():
    try:
        import sentence_transformers  # noqa: F401
        # If installed, provider initializes cleanly
        provider = SentenceTransformerEmbeddingProvider()
        assert provider.dimension > 0
    except ImportError:
        # If not installed, raises clear configuration error
        with pytest.raises(EmbeddingConfigurationError) as exc_info:
            SentenceTransformerEmbeddingProvider()
        assert "sentence-transformers" in str(exc_info.value)

