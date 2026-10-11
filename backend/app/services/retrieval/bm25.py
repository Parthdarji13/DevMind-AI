"""
BM25 lexical search and code identifier retrieval.
Ref: PRD Section 6 (FR-06), Section 7; Step 17 of execution guide.
Implements Okapi BM25 with code-aware sub-tokenization and symbol name boosting.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
import math
import re
from typing import Optional

from ...models.chunk import CodeChunk


@dataclass
class SearchResult:
    chunk_id: str
    score: float
    chunk: CodeChunk
    lexical_score: Optional[float] = None
    vector_score: Optional[float] = None
    retrieval_method: str = "lexical"


def tokenize_code(text: str) -> list[str]:
    """
    Code-aware tokenizer:
    Splits text on whitespace and punctuation, extracts words,
    and splits camelCase and snake_case while preserving original identifiers.
    """
    if not text:
        return []

    tokens: list[str] = []
    # Extract candidate identifiers and words
    raw_tokens = re.findall(r"[A-Za-z0-9_]+", text)

    for tok in raw_tokens:
        tok_lower = tok.lower()
        tokens.append(tok_lower)

        # Snake_case split
        if "_" in tok:
            subparts = tok.split("_")
            for sp in subparts:
                if sp:
                    tokens.append(sp.lower())

        # CamelCase split (e.g. getUserProfile -> get, User, Profile)
        camel_parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", tok)
        if len(camel_parts) > 1:
            for cp in camel_parts:
                tokens.append(cp.lower())

    return tokens


class BM25Index:
    """
    Okapi BM25 index over code chunks.
    Parameters: k1=1.5, b=0.75.
    """

    def __init__(self, chunks: list[CodeChunk], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.chunks = chunks
        self.corpus_size = len(chunks)

        self.doc_lengths: list[int] = []
        self.doc_token_counts: list[Counter] = []
        self.inverted_index: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.idf: dict[str, float] = {}

        self.avg_doc_len = 0.0
        self._build_index()

    def _build_index(self) -> None:
        if not self.chunks:
            return

        total_tokens = 0
        doc_frequencies: Counter = Counter()

        for idx, chunk in enumerate(self.chunks):
            # Tokenize content, file path, and symbol name
            extra_text = f"{chunk.file_path} {chunk.symbol_name or ''}"
            tokens = tokenize_code(f"{chunk.content} {extra_text}")
            d_len = len(tokens)
            self.doc_lengths.append(d_len)
            total_tokens += d_len

            counts = Counter(tokens)
            self.doc_token_counts.append(counts)

            for term, count in counts.items():
                self.inverted_index[term].append((idx, count))
                doc_frequencies[term] += 1

        self.avg_doc_len = total_tokens / self.corpus_size if self.corpus_size > 0 else 1.0

        # Precompute Okapi IDF
        for term, df in doc_frequencies.items():
            # Standard BM25 IDF with smoothing
            val = math.log((self.corpus_size - df + 0.5) / (df + 0.5) + 1.0)
            self.idf[term] = max(0.01, val)

    def search(
        self,
        query: str,
        top_k: int = 10,
        file_path: Optional[str] = None,
        path_prefix: Optional[str] = None,
        language: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        Executes BM25 query against indexed chunks.
        Applies bonuses for exact symbol name and file path matches.
        Supports metadata filtering by file_path, path_prefix, and language.
        """
        if not self.chunks or not query or not query.strip():
            return []

        query_tokens = tokenize_code(query)
        if not query_tokens:
            return []

        scores: dict[int, float] = defaultdict(float)

        for term in query_tokens:
            idf = self.idf.get(term, 0.0)
            if idf <= 0.0:
                continue

            postings = self.inverted_index.get(term, [])
            for doc_idx, tf in postings:
                d_len = self.doc_lengths[doc_idx]
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (d_len / self.avg_doc_len))
                term_score = idf * (numerator / denominator)
                scores[doc_idx] += term_score

        # Apply metadata filters and bonuses
        query_lower = query.lower()
        for doc_idx, score in list(scores.items()):
            chunk = self.chunks[doc_idx]

            # Filters
            if file_path and chunk.file_path != file_path:
                scores.pop(doc_idx, None)
                continue
            if path_prefix and not chunk.file_path.startswith(path_prefix):
                scores.pop(doc_idx, None)
                continue
            if language and chunk.language.lower() != language.lower():
                scores.pop(doc_idx, None)
                continue

            # Symbol name boost: if chunk's symbol matches query term exactly
            if chunk.symbol_name and chunk.symbol_name.lower() in query_lower:
                scores[doc_idx] += 2.5

            # File path / filename boost: if file path is referenced in query
            p_name = chunk.file_path.split("/")[-1].lower()
            if p_name in query_lower:
                scores[doc_idx] += 3.0

        # Sort and return top_k
        sorted_indices = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        return [
            SearchResult(
                chunk_id=self.chunks[doc_idx].chunk_id,
                score=round(score, 4),
                chunk=self.chunks[doc_idx],
                lexical_score=round(score, 4),
                retrieval_method="lexical",
            )
            for doc_idx, score in sorted_indices
            if score > 0
        ]
