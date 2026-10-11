"""
Hybrid retrieval combining lexical (BM25) and vector (semantic) search using Reciprocal Rank Fusion (RRF).
Ref: PRD Section 6 (FR-06), Section 7; Step 19 of execution guide.
Combines exact identifier matching and semantic conceptual retrieval with deduplication,
configurable weighting, top-k limiting, context-size budgeting, and graceful fallback.
"""
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Optional

from ...core.config import get_settings
from ...models.chunk import CodeChunk
from ..indexing.embeddings import (
    BaseEmbeddingProvider,
    get_embedding_provider,
)
from ..indexing.storage import IndexStorageManager, PersistentIndexStore
from .bm25 import BM25Index, SearchResult
from .vector import (
    EmbeddingNotAvailableError,
    RepositoryNotIndexedError,
    VectorRetrievalError,
    VectorSearchIndex,
)

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Combines BM25 lexical search and dense vector search via Reciprocal Rank Fusion (RRF).
    RRF formula: RRF_score(d) = sum( weight_m / (rrf_k + rank_m(d)) ) for rankers m.
    """

    def __init__(
        self,
        repo_id: str,
        bm25_index: BM25Index,
        vector_index: Optional[VectorSearchIndex] = None,
        rrf_k: int = 60,
        weight_lexical: float = 1.0,
        weight_vector: float = 1.0,
    ):
        self.repo_id = repo_id
        self.bm25_index = bm25_index
        self.vector_index = vector_index
        self.rrf_k = rrf_k
        self.weight_lexical = weight_lexical
        self.weight_vector = weight_vector

    @classmethod
    def from_store(
        cls,
        store: PersistentIndexStore,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
        rrf_k: int = 60,
        weight_lexical: float = 1.0,
        weight_vector: float = 1.0,
    ) -> "HybridRetriever":
        """Instantiates HybridRetriever from a PersistentIndexStore."""
        if not store.exists():
            raise RepositoryNotIndexedError(
                f"Repository '{store.repo_id}' has not been indexed yet or index is missing."
            )

        chunks = store.get_chunks()
        bm25 = BM25Index(chunks)

        vector_idx: Optional[VectorSearchIndex] = None
        vectors = store.get_vectors()
        if vectors is not None and len(vectors) > 0 and len(chunks) == len(vectors):
            try:
                vector_idx = VectorSearchIndex(
                    repo_id=store.repo_id,
                    chunks=chunks,
                    vectors=vectors,
                    embedding_provider=embedding_provider,
                )
            except Exception as e:
                logger.warning(
                    f"Could not initialize vector index for repo {store.repo_id}: {e}. "
                    "Falling back to BM25-only."
                )

        return cls(
            repo_id=store.repo_id,
            bm25_index=bm25,
            vector_index=vector_idx,
            rrf_k=rrf_k,
            weight_lexical=weight_lexical,
            weight_vector=weight_vector,
        )

    @classmethod
    def from_repo_id(
        cls,
        repo_id: str,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
        custom_base_dir: Optional[Path] = None,
        rrf_k: int = 60,
        weight_lexical: float = 1.0,
        weight_vector: float = 1.0,
    ) -> "HybridRetriever":
        """Loads repository index from disk and builds a HybridRetriever."""
        store = PersistentIndexStore(repo_id, custom_base_dir=custom_base_dir)
        return cls.from_store(
            store=store,
            embedding_provider=embedding_provider,
            rrf_k=rrf_k,
            weight_lexical=weight_lexical,
            weight_vector=weight_vector,
        )

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        file_path: Optional[str] = None,
        path_prefix: Optional[str] = None,
        language: Optional[str] = None,
        max_total_chars: Optional[int] = None,
    ) -> list[SearchResult]:
        """
        Executes hybrid retrieval:
        1. Runs BM25 lexical search.
        2. Runs vector semantic search (with graceful fallback if unavailable).
        3. Fuses ranks using Reciprocal Rank Fusion (RRF).
        4. Deduplicates chunks by chunk_id.
        5. Limits by top_k and optional total character context budget.
        """
        if not query or not query.strip():
            return []

        # Candidate multiplier to ensure ample pool for rank fusion
        candidate_k = max(top_k * 3, 20)

        # 1. Lexical search (BM25)
        lexical_results = self.bm25_index.search(
            query=query,
            top_k=candidate_k,
            file_path=file_path,
            path_prefix=path_prefix,
            language=language,
        )

        # 2. Vector search (Semantic) with graceful fallback
        vector_results: list[SearchResult] = []
        if self.vector_index is not None:
            try:
                vector_results = self.vector_index.search(
                    query=query,
                    top_k=candidate_k,
                    file_path=file_path,
                    path_prefix=path_prefix,
                    language=language,
                )
            except (EmbeddingNotAvailableError, VectorRetrievalError) as e:
                logger.warning(
                    f"Vector search failed or provider unavailable for query '{query}': {e}. "
                    "Proceeding with BM25-only results."
                )
                vector_results = []
            except Exception as e:
                logger.error(
                    f"Unexpected vector search error: {e}. Proceeding with BM25 results.",
                    exc_info=True,
                )
                vector_results = []

        # If both engines return nothing, return empty
        if not lexical_results and not vector_results:
            return []

        # 3. Reciprocal Rank Fusion (RRF)
        # Map: chunk_id -> dict with aggregated scores and chunk reference
        fused_map: dict[str, dict] = {}

        # Process Lexical rankings
        for rank_0, res in enumerate(lexical_results):
            rank = rank_0 + 1
            cid = res.chunk_id
            score_contrib = self.weight_lexical / (self.rrf_k + rank)

            if cid not in fused_map:
                fused_map[cid] = {
                    "chunk": res.chunk,
                    "rrf_score": score_contrib,
                    "lexical_score": res.score,
                    "vector_score": None,
                    "in_lexical": True,
                    "in_vector": False,
                }
            else:
                fused_map[cid]["rrf_score"] += score_contrib
                fused_map[cid]["lexical_score"] = res.score
                fused_map[cid]["in_lexical"] = True

        # Process Vector rankings
        for rank_0, res in enumerate(vector_results):
            rank = rank_0 + 1
            cid = res.chunk_id
            score_contrib = self.weight_vector / (self.rrf_k + rank)

            if cid not in fused_map:
                fused_map[cid] = {
                    "chunk": res.chunk,
                    "rrf_score": score_contrib,
                    "lexical_score": None,
                    "vector_score": res.score,
                    "in_lexical": False,
                    "in_vector": True,
                }
            else:
                fused_map[cid]["rrf_score"] += score_contrib
                fused_map[cid]["vector_score"] = res.score
                fused_map[cid]["in_vector"] = True

        # 4. Sort unique items by fused RRF score descending
        ranked_candidates = sorted(
            fused_map.items(),
            key=lambda item: item[1]["rrf_score"],
            reverse=True,
        )

        # 5. Apply top_k and optional character/context limit
        final_results: list[SearchResult] = []
        cumulative_chars = 0

        for cid, info in ranked_candidates:
            chunk: CodeChunk = info["chunk"]
            chunk_chars = chunk.char_count or len(chunk.content)

            # Check character budget if specified
            if max_total_chars is not None and (cumulative_chars + chunk_chars > max_total_chars):
                # If we already have at least 1 result, stop adding chunks to respect context budget
                if final_results:
                    break

            method = (
                "hybrid"
                if (info["in_lexical"] and info["in_vector"])
                else ("lexical" if info["in_lexical"] else "vector")
            )

            final_results.append(
                SearchResult(
                    chunk_id=cid,
                    score=round(info["rrf_score"], 6),
                    chunk=chunk,
                    lexical_score=info["lexical_score"],
                    vector_score=info["vector_score"],
                    retrieval_method=method,
                )
            )

            cumulative_chars += chunk_chars
            if len(final_results) >= top_k:
                break

        return final_results


class HybridRetrievalManager:
    """
    Manages cached HybridRetriever instances per repository.
    """

    def __init__(
        self,
        storage_manager: Optional[IndexStorageManager] = None,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
    ):
        self.storage_manager = storage_manager or IndexStorageManager()
        self.embedding_provider = embedding_provider
        self._retrievers: dict[str, HybridRetriever] = {}

    def get_retriever(
        self,
        repo_id: str,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
        reload: bool = False,
    ) -> HybridRetriever:
        """Retrieves or instantiates HybridRetriever for a repository."""
        if not reload and repo_id in self._retrievers:
            return self._retrievers[repo_id]

        store = self.storage_manager.get_store(repo_id)
        if not store.exists():
            raise RepositoryNotIndexedError(
                f"Repository '{repo_id}' has not been indexed yet."
            )

        provider = embedding_provider or self.embedding_provider
        retriever = HybridRetriever.from_store(store, embedding_provider=provider)
        self._retrievers[repo_id] = retriever
        return retriever

    def retrieve(
        self,
        repo_id: str,
        query: str,
        top_k: int = 10,
        file_path: Optional[str] = None,
        path_prefix: Optional[str] = None,
        language: Optional[str] = None,
        max_total_chars: Optional[int] = None,
    ) -> list[SearchResult]:
        """Convenience method to retrieve from a repository directly."""
        retriever = self.get_retriever(repo_id)
        return retriever.retrieve(
            query=query,
            top_k=top_k,
            file_path=file_path,
            path_prefix=path_prefix,
            language=language,
            max_total_chars=max_total_chars,
        )

    def invalidate(self, repo_id: str) -> None:
        """Evicts a retriever from memory cache."""
        self._retrievers.pop(repo_id, None)
