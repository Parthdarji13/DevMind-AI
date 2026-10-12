"""
Strict citation extraction, validation, and snippet slicing for DevMind AI.
Ref: PRD Section 6 (FR-07, FR-08, FR-09), Section 7, Section 8; Step 22 of execution guide.
Enforces:
1. Every citation must map to a verified file path in retrieved chunk metadata.
2. Citation line range must overlap with the chunk's physical line boundaries.
3. Extracts verbatim source snippet from the chunk for UI code viewer.
4. Drops or flags hallucinated files and out-of-bounds line numbers.
"""
from dataclasses import dataclass
from enum import Enum
import re
from typing import Optional, Union

from ...models.chat import Citation
from ...models.chunk import CodeChunk
from ..retrieval.bm25 import SearchResult


class CitationStatus(str, Enum):
    VALID = "valid"
    UNKNOWN_FILE = "unknown_file"
    OUT_OF_BOUNDS = "out_of_bounds"
    INVALID_RANGE = "invalid_range"


@dataclass
class ValidationDetail:
    citation: Citation
    status: CitationStatus
    reason: str
    matched_chunk_id: Optional[str] = None


@dataclass
class CitationValidationReport:
    valid_citations: list[Citation]
    invalid_citations: list[ValidationDetail]
    total_extracted: int


class CitationValidator:
    """
    Validates LLM-generated citations against retrieved chunk metadata.
    Guarantees that no hallucinated files or line numbers are exposed to users.
    """

    CITATION_PATTERNS = [
        # 1. [File: path/to/file.py, Lines: 10-25] or [File: path/to/file.py, Line: 10]
        re.compile(
            r"\[(?:File:\s*)?([A-Za-z0-9_\-\./\\]+),\s*Lines?:?\s*(\d+)(?:-(\d+))?.*?\]",
            re.IGNORECASE,
        ),
        # 2. [path/to/file.py:10-25] or [path/to/file.py:10]
        re.compile(
            r"\[([A-Za-z0-9_\-\./\\]+\.[a-zA-Z0-9_]+):(\d+)(?:-(\d+))?\]",
        ),
        # 3. `path/to/file.py:10-25` or `path/to/file.py:10`
        re.compile(
            r"`([A-Za-z0-9_\-\./\\]+\.[a-zA-Z0-9_]+):(\d+)(?:-(\d+))?`",
        ),
    ]

    def extract_raw_citations(self, text: str) -> list[Citation]:
        """Extracts candidate citations from model response text across supported syntaxes."""
        if not text:
            return []

        candidates: list[Citation] = []
        seen: set[tuple[str, int, int]] = set()

        for pattern in self.CITATION_PATTERNS:
            for m in pattern.finditer(text):
                path = m.group(1).replace("\\", "/").strip()
                start = int(m.group(2))
                end = int(m.group(3)) if m.group(3) else start

                # Basic sanity
                if start > end:
                    start, end = end, start

                key = (path, start, end)
                if key not in seen:
                    seen.add(key)
                    candidates.append(Citation(file_path=path, start_line=start, end_line=end))

        return candidates

    def validate_and_slice(
        self,
        citations: list[Citation],
        chunks: list[Union[CodeChunk, SearchResult]],
    ) -> CitationValidationReport:
        """
        Validates citations against retrieved chunks:
        - Rejects files not in retrieved chunks.
        - Rejects line ranges not overlapping with chunk line boundaries.
        - Slices exact verbatim snippet for valid citations.
        """
        chunk_list: list[CodeChunk] = [
            c.chunk if isinstance(c, SearchResult) else c for c in chunks
        ]

        # Index chunks by normalized file_path for fast lookup
        chunks_by_path: dict[str, list[CodeChunk]] = {}
        for chunk in chunk_list:
            norm_path = chunk.file_path.replace("\\", "/").strip()
            chunks_by_path.setdefault(norm_path, []).append(chunk)

        valid_list: list[Citation] = []
        invalid_list: list[ValidationDetail] = []

        for cit in citations:
            norm_cit_path = cit.file_path.replace("\\", "/").strip()

            # Rule 1: File path existence check
            candidate_chunks = chunks_by_path.get(norm_cit_path)
            if not candidate_chunks:
                # Try matching by filename suffix if relative path lacks root
                matched_suffix = [
                    c for c in chunk_list
                    if c.file_path.endswith(norm_cit_path) or norm_cit_path.endswith(c.file_path)
                ]
                if matched_suffix:
                    candidate_chunks = matched_suffix
                    norm_cit_path = matched_suffix[0].file_path
                else:
                    invalid_list.append(
                        ValidationDetail(
                            citation=cit,
                            status=CitationStatus.UNKNOWN_FILE,
                            reason=f"File '{cit.file_path}' does not exist in retrieved evidence chunks.",
                        )
                    )
                    continue

            # Rule 2: Line range overlap check
            matched_chunk: Optional[CodeChunk] = None
            for c in candidate_chunks:
                # Overlap test: not (cit.end_line < c.start_line or cit.start_line > c.end_line)
                if not (cit.end_line < c.start_line or cit.start_line > c.end_line):
                    matched_chunk = c
                    break

            if not matched_chunk:
                invalid_list.append(
                    ValidationDetail(
                        citation=cit,
                        status=CitationStatus.OUT_OF_BOUNDS,
                        reason=(
                            f"Lines {cit.start_line}-{cit.end_line} fall outside "
                            f"the line boundaries of retrieved chunk(s) for '{cit.file_path}'."
                        ),
                    )
                )
                continue

            # Rule 3: Slice verbatim snippet from chunk content
            chunk_lines = matched_chunk.content.splitlines()
            # Calculate 0-based slice offsets relative to chunk.start_line
            slice_start = max(0, cit.start_line - matched_chunk.start_line)
            slice_end = min(len(chunk_lines), cit.end_line - matched_chunk.start_line + 1)

            if slice_start < len(chunk_lines):
                snippet = "\n".join(chunk_lines[slice_start:slice_end])
            else:
                snippet = matched_chunk.content[:200]

            valid_cit = Citation(
                file_path=norm_cit_path,
                start_line=cit.start_line,
                end_line=cit.end_line,
                snippet=snippet,
                chunk_id=matched_chunk.chunk_id,
            )
            valid_list.append(valid_cit)

        return CitationValidationReport(
            valid_citations=valid_list,
            invalid_citations=invalid_list,
            total_extracted=len(citations),
        )

    def process_text_citations(
        self,
        text: str,
        chunks: list[Union[CodeChunk, SearchResult]],
    ) -> CitationValidationReport:
        """Convenience method: extracts from text and validates against chunks."""
        raw = self.extract_raw_citations(text)
        return self.validate_and_slice(raw, chunks)
