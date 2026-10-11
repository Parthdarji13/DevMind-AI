"""
Vector semantic retrieval for DevMind AI.
Ref: PRD Section 6 (FR-06), Section 7, Section 8; Step 18 of execution guide.
Implements cosine similarity over persistent vector embeddings with repository and metadata filters.
Explicitly reports errors on unindexed repos, dimension mismatches, and embedding failures.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union
import numpy as np

from ...core.config import get_settings
from ...models.chunk import CodeChunk
from ..indexing.embeddings import (
    BaseEmbeddingProvider,
    EmbeddingProviderError,
    get_embedding_provider,
)
from ..indexing.storage import IndexStorageManager, PersistentIndexStore
from .bm25 import SearchResult


class VectorRetrievalError(Exception):
    """Base exception for vector retrieval errors."""
    pass


class RepositoryNotIndexedError(VectorRetrievalError):
    """Raised when querying a repository that has not been indexed."""
    pass


class DimensionMismatchError(VectorRetrievalError):
    """Raised when query vector dimension does not match stored vector dimension."""
    pass


class EmbeddingNotAvailableError(VectorRetrievalError):
    """Raised when embedding provider is missing or cannot generate query embeddings."""
    pass


class VectorSearchIndex:
    """
    Vector search index supporting cosine similarity search,
    per-repository isolation, and metadata filtering.
    """

    def __init__(
        self,
        repo_id: str,
        chunks: list[CodeChunk],
        vectors: Union[np.ndarray, list[list[float]]],
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
    ):
        self.repo_id = repo_id
        self.chunks = chunks
        self.embedding_provider = embedding_provider

        if isinstance(vectors, list):
            self.vectors = np.array(vectors, dtype=np.float32) if vectors else np.empty((0, 0), dtype=np.float32)
        else:
            self.vectors = vectors.astype(np.float32)

        # Enforce consistency between chunks and vectors
        if len(self.chunks) != len(self.vectors):
            raise ValueError(
                f"Chunk count ({len(self.chunks)}) does not match vector count ({len(self.vectors)})."
            )

        self.dimension = int(self.vectors.shape[1]) if self.vectors.ndim == 2 and self.vectors.shape[0] > 0 else 0

        # Pre-normalize stored vectors to unit length for fast dot-product cosine similarity
        if self.vectors.shape[0] > 0 and self.dimension > 0:
            norms = np.linalg.norm(self.vectors, axis=1, keepdims=True)
            # Avoid division by zero
            norms[norms == 0] = 1.0
            self.normalized_vectors = self.vectors / norms
        else:
            self.normalized_vectors = self.vectors

    @property
    def corpus_size(self) -> int:
        return len(self.chunks)

    @classmethod
    def from_store(
        cls,
        store: PersistentIndexStore,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
    ) -> "VectorSearchIndex":
        """Builds a VectorSearchIndex from a PersistentIndexStore instance."""
        if not store.exists():
            raise RepositoryNotIndexedError(
                f"Repository '{store.repo_id}' has not been indexed yet or index is missing."
            )
        chunks = store.chunks
        vectors = store.vectors
        if vectors is None:
            vectors = np.empty((0, 0), dtype=np.float32)
        return cls(
            repo_id=store.repo_id,
            chunks=chunks,
            vectors=vectors,
            embedding_provider=embedding_provider,
        )

    @classmethod
    def from_repo_id(
        cls,
        repo_id: str,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
        custom_base_dir: Optional[Path] = None,
    ) -> "VectorSearchIndex":
        """Loads persistent index from disk for repo_id and initializes VectorSearchIndex."""
        store = PersistentIndexStore(repo_id, custom_base_dir=custom_base_dir)
        return cls.from_store(store, embedding_provider=embedding_provider)

    def search(
        self,
        query: str,
        top_k: int = 10,
        file_path: Optional[str] = None,
        path_prefix: Optional[str] = None,
        language: Optional[str] = None,
        min_score: float = -1.0,
    ) -> list[SearchResult]:
        """
        Executes semantic search with natural language query.
        Embeds the query using the configured embedding provider.
        """
        if not query or not query.strip():
            return []

        if self.corpus_size == 0 or self.dimension == 0:
            return []

        if self.embedding_provider is None:
            raise EmbeddingNotAvailableError(
                "No embedding provider configured for vector search. "
                "Provide an embedding provider or use search_by_vector directly."
            )

        try:
            query_vector = self.embedding_provider.embed_query(query)
        except EmbeddingProviderError as e:
            raise VectorRetrievalError(f"Embedding generation failed: {str(e)}") from e
        except Exception as e:
            raise VectorRetrievalError(f"Unexpected error embedding query: {str(e)}") from e

        return self.search_by_vector(
            query_vector=query_vector,
            top_k=top_k,
            file_path=file_path,
            path_prefix=path_prefix,
            language=language,
            min_score=min_score,
        )

    def search_by_vector(
        self,
        query_vector: Union[list[float], np.ndarray],
        top_k: int = 10,
        file_path: Optional[str] = None,
        path_prefix: Optional[str] = None,
        language: Optional[str] = None,
        min_score: float = -1.0,
    ) -> list[SearchResult]:
        """
        Executes cosine similarity search directly using a precomputed query vector.
        Supports repository and chunk metadata filters.
        """
        if self.corpus_size == 0 or self.dimension == 0:
            return []

        q_vec = np.array(query_vector, dtype=np.float32)
        if q_vec.ndim != 1:
            q_vec = q_vec.flatten()

        if q_vec.shape[0] != self.dimension:
            raise DimensionMismatchError(
                f"Query vector dimension ({q_vec.shape[0]}) does not match "
                f"index embedding dimension ({self.dimension})."
            )

        # Normalize query vector to unit norm
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []
        q_unit = q_vec / q_norm

        # Apply candidate metadata filters
        candidate_indices: list[int] = []
        for i, chunk in enumerate(self.chunks):
            if file_path and chunk.file_path != file_path:
                continue
            if path_prefix and not chunk.file_path.startswith(path_prefix):
                continue
            if language and chunk.language.lower() != language.lower():
                continue
            candidate_indices.append(i)

        if not candidate_indices:
            return []

        # Compute cosine similarity (dot product of normalized vectors)
        cand_matrix = self.normalized_vectors[candidate_indices]
        sim_scores = np.dot(cand_matrix, q_unit)

        # Rank candidates by score descending
        results: list[SearchResult] = []
        # Sort candidate indices by sim_scores descending
        sorted_order = np.argsort(-sim_scores)

        for rank_idx in sorted_order:
            orig_idx = candidate_indices[rank_idx]
            score = float(sim_scores[rank_idx])
            # Clamp numerical precision artifacts to [-1.0, 1.0]
            score = max(-1.0, min(1.0, score))

            if score < min_score:
                continue

            results.append(
                SearchResult(
                    chunk_id=self.chunks[orig_idx].chunk_id,
                    score=score,
                    chunk=self.chunks[orig_idx],
                    vector_score=score,
                    retrieval_method="vector",
                )
            )

            if len(results) >= top_k:
                break

        return results


class VectorSearchManager:
    """
    Manages cached VectorSearchIndex instances across isolated repositories.
    """

    def __init__(
        self,
        storage_manager: Optional[IndexStorageManager] = None,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
    ):
        self.storage_manager = storage_manager or IndexStorageManager()
        self.embedding_provider = embedding_provider
        self._indices: dict[str, VectorSearchIndex] = {}

    def get_index(
        self,
        repo_id: str,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
        reload: bool = False,
    ) -> VectorSearchIndex:
        """Retrieves or loads the VectorSearchIndex for the given repo_id."""
        if not reload and repo_id in self._indices:
            return self._indices[repo_id]

        store = self.storage_manager.get_store(repo_id)
        if not store.exists():
            raise RepositoryNotIndexedError(
                f"Repository '{repo_id}' is not indexed or index files are missing."
            )

        provider = embedding_provider or self.embedding_provider
        idx = VectorSearchIndex.from_store(store, embedding_provider=provider)
        self._indices[repo_id] = idx
        return idx

    def search(
        self,
        repo_id: str,
        query: str,
        top_k: int = 10,
        file_path: Optional[str] = None,
        path_prefix: Optional[str] = None,
        language: Optional[str] = None,
    ) -> list[SearchResult]:
        """Convenience method to query a repository vector index directly."""
        idx = self.get_index(repo_id)
        return idx.search(
            query=query,
            top_k=top_k,
            file_path=file_path,
            path_prefix=path_prefix,
            language=language,
        )

    def invalidate(self, repo_id: str) -> None:
        """Removes a repository index from the memory cache."""
        self._indices.pop(repo_id, None)
