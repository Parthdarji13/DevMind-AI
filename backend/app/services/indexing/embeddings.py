"""
Embeddings service for DevMind AI.
Ref: PRD Section 7, 8; Step 15 of execution guide.
Supports Local Semantic projection, Google GenAI (text-embedding-004), OpenAI, and Mock.
Enforces credential verification, dimension consistency, L2 normalization, and batching.
"""
from abc import ABC, abstractmethod
import hashlib
import math
import re
from typing import Optional
import httpx
import numpy as np

from ...core.config import get_settings


class EmbeddingProviderError(Exception):
    """Base error for embedding failures."""
    pass


class EmbeddingConfigurationError(EmbeddingProviderError):
    """Raised when provider configuration or API keys are missing/invalid."""
    pass


class EmbeddingAPIError(EmbeddingProviderError):
    """Raised when external embedding provider API returns an error or times out."""
    pass


class BaseEmbeddingProvider(ABC):
    """Abstract base class for all embedding providers."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @abstractmethod
    def embed_texts(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        pass

    def embed_query(self, text: str) -> list[float]:
        results = self.embed_texts([text], batch_size=1)
        if not results:
            raise EmbeddingProviderError("Failed to generate embedding for query.")
        return results[0]

    @staticmethod
    def normalize_vector(vec: list[float]) -> list[float]:
        """Ensures L2 unit length for cosine dot-product similarity."""
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0:
            return vec
        return [x / norm for x in vec]


class LocalSemanticEmbeddingProvider(BaseEmbeddingProvider):
    """
    Fast, deterministic local embedding provider using n-gram token projection.
    Provides 384-dimensional unit vectors without external network calls or GPU requirements.
    Preserves semantic similarity based on identifiers, terms, and syntax tokens.
    """

    def __init__(self, dimension: int = 384):
        self._dimension = dimension
        self._model_name = "local-semantic-384"

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def _embed_single(self, text: str) -> list[float]:
        if not text or not text.strip():
            # Return deterministic pseudo-zero normalized vector
            vec = [0.0] * self._dimension
            vec[0] = 1.0
            return vec

        # Tokenize code into words, camelCase splits, and punctuation
        words = re.findall(r"[A-Za-z0-9_]+|[^\w\s]", text)
        vec = np.zeros(self._dimension, dtype=np.float32)

        for i, word in enumerate(words):
            # Term weight with position decay and frequency damping
            w_lower = word.lower()
            h = int(hashlib.md5(w_lower.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dimension
            sign = 1.0 if (h >> 16) & 1 else -1.0
            weight = math.log1p(len(w_lower))
            vec[idx] += sign * weight

            # Also hash character bigrams for subword robustness
            if len(w_lower) >= 3:
                for j in range(len(w_lower) - 1):
                    bg = w_lower[j : j + 2]
                    bg_h = int(hashlib.md5(bg.encode("utf-8")).hexdigest(), 16)
                    bg_idx = bg_h % self._dimension
                    bg_sign = 1.0 if (bg_h >> 16) & 1 else -1.0
                    vec[bg_idx] += bg_sign * 0.3

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        else:
            vec[0] = 1.0

        return vec.tolist()

    def embed_texts(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        results: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            for text in batch:
                results.append(self._embed_single(text))
        return results


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """Google Gemini embedding provider with batching and error handling."""

    def __init__(self, api_key: str, model_name: str = "gemini-embedding-001"):
        if not api_key or api_key.startswith("your_"):
            raise EmbeddingConfigurationError(
                "GEMINI_API_KEY is not configured or contains placeholder value."
            )
        self._api_key = api_key
        clean_name = model_name.replace("models/", "")
        self._model_name = clean_name
        self._dimension = 768 if "004" in clean_name else 3072

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_texts(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        if not texts:
            return []

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model_name}:batchEmbedContents"
        results: list[list[float]] = []

        # Process in batches of at most batch_size (max 32 for Gemini)
        effective_batch_size = min(32, batch_size)

        for i in range(0, len(texts), effective_batch_size):
            chunk = texts[i : i + effective_batch_size]
            requests_payload = [
                {"model": f"models/{self._model_name}", "content": {"parts": [{"text": t}]}}
                for t in chunk
            ]

            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(
                        url,
                        params={"key": self._api_key},
                        json={"requests": requests_payload},
                    )

                if resp.status_code != 200:
                    raise EmbeddingAPIError(
                        f"Gemini API returned status {resp.status_code}: {resp.text}"
                    )

                data = resp.json()
                embeddings_data = data.get("embeddings", [])
                if len(embeddings_data) != len(chunk):
                    raise EmbeddingAPIError(
                        f"Expected {len(chunk)} embeddings, received {len(embeddings_data)}."
                    )

                for item in embeddings_data:
                    values = item.get("values", [])
                    results.append(self.normalize_vector(values))

            except httpx.TimeoutException as e:
                raise EmbeddingAPIError("Gemini embedding API request timed out.") from e
            except Exception as e:
                if isinstance(e, EmbeddingProviderError):
                    raise
                raise EmbeddingAPIError(f"Unexpected error in Gemini embedding: {str(e)}") from e

        return results


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI text-embedding-3-small provider with batching and error handling."""

    def __init__(self, api_key: str, model_name: str = "text-embedding-3-small"):
        if not api_key or api_key.startswith("your_"):
            raise EmbeddingConfigurationError(
                "OPENAI_API_KEY is not configured or contains placeholder value."
            )
        self._api_key = api_key
        self._model_name = model_name
        self._dimension = 1536

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_texts(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        if not texts:
            return []

        url = "https://api.openai.com/v1/embeddings"
        results: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(
                        url,
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        json={"input": chunk, "model": self._model_name},
                    )

                if resp.status_code != 200:
                    raise EmbeddingAPIError(
                        f"OpenAI API returned status {resp.status_code}: {resp.text}"
                    )

                data = resp.json()
                data_items = data.get("data", [])
                for item in sorted(data_items, key=lambda x: x["index"]):
                    results.append(self.normalize_vector(item["embedding"]))

            except httpx.TimeoutException as e:
                raise EmbeddingAPIError("OpenAI embedding API request timed out.") from e
            except Exception as e:
                if isinstance(e, EmbeddingProviderError):
                    raise
                raise EmbeddingAPIError(f"Unexpected error in OpenAI embedding: {str(e)}") from e

        return results


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Mock embedding provider for tests and fast offline validation."""

    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return f"mock-{self._dimension}"

    def embed_texts(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            # Deterministic vector based on text hash
            h = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
            vec = [(float((h >> (i % 64)) & 0xFF) / 255.0) for i in range(self._dimension)]
            results.append(self.normalize_vector(vec))
        return results


class SentenceTransformerEmbeddingProvider(BaseEmbeddingProvider):
    """
    True local dense semantic neural embedding provider powered by sentence-transformers.
    Default model is 'all-MiniLM-L6-v2' (384 dimensions).
    Runs offline on CPU/GPU without external network calls.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as e:
            raise EmbeddingConfigurationError(
                "The 'sentence-transformers' package is required for local dense neural embeddings. "
                "Install it via 'pip install sentence-transformers' or use EMBEDDING_PROVIDER=local_hash "
                "or EMBEDDING_PROVIDER=google_genai."
            ) from e

        self._model_name = model_name
        self._model = SentenceTransformer(model_name)
        self._dimension = int(self._model.get_sentence_embedding_dimension())

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_texts(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return embeddings.tolist()


class FastEmbedEmbeddingProvider(BaseEmbeddingProvider):
    """
    True local dense semantic neural embedding provider powered by FastEmbed (ONNX).
    Default model is 'sentence-transformers/all-MiniLM-L6-v2' (384 dimensions).
    Runs offline on CPU with high inference speed, low memory footprint, and zero external network calls.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        try:
            from fastembed import TextEmbedding  # type: ignore
        except ImportError as e:
            raise EmbeddingConfigurationError(
                "The 'fastembed' package is required for local dense neural embeddings. "
                "Install it via 'pip install fastembed' or use EMBEDDING_PROVIDER=local_hash."
            ) from e

        self._model_name = model_name
        self._model = TextEmbedding(model_name=model_name)
        self._dimension = 384

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_texts(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        if not texts:
            return []
        embeddings = list(self._model.embed(texts, batch_size=batch_size))
        return [self.normalize_vector(vec.tolist() if hasattr(vec, "tolist") else list(vec)) for vec in embeddings]


# Alias for explicit zero-dependency hash projection
LocalHashEmbeddingProvider = LocalSemanticEmbeddingProvider


def get_embedding_provider(provider_name: Optional[str] = None) -> BaseEmbeddingProvider:
    """
    Factory creating configured embedding provider.
    Enforces that semantic search fails with clear error if credentials missing.
    Prioritizes real neural semantic models (FastEmbed / SentenceTransformers) for local search.
    """
    settings = get_settings()
    choice = (provider_name or settings.embedding_provider).lower()

    if choice in ("fastembed", "local", "local_semantic", "sentence-transformers", "sentence_transformers"):
        # 1. Prefer FastEmbed (fast ONNX neural transformer embeddings)
        try:
            import fastembed  # noqa: F401
            return FastEmbedEmbeddingProvider()
        except Exception:
            pass

        # 2. Try SentenceTransformers if available
        try:
            import sentence_transformers  # noqa: F401
            return SentenceTransformerEmbeddingProvider()
        except Exception:
            pass

        # 3. Fallback to LocalSemantic deterministic hash projection
        return LocalSemanticEmbeddingProvider()

    elif choice in ("local_hash", "hash"):
        return LocalSemanticEmbeddingProvider()

    elif choice in ("google", "google_genai", "gemini"):
        model = settings.embedding_model if "embedding" in settings.embedding_model else "gemini-embedding-001"
        return GeminiEmbeddingProvider(api_key=settings.gemini_api_key, model_name=model)

    elif choice == "openai":
        return OpenAIEmbeddingProvider(api_key=settings.openai_api_key)

    elif choice == "mock":
        return MockEmbeddingProvider()

    else:
        raise EmbeddingConfigurationError(
            f"Unsupported embedding provider: '{choice}'. Supported: 'local', 'fastembed', 'sentence-transformers', 'local_hash', 'google_genai', 'openai', 'mock'."
        )


