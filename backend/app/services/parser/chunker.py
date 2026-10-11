"""
Syntax-aware and line-bounded code chunking engine.
Ref: PRD Section 6 (FR-04, FR-07), Section 8; Step 14 of execution guide.
Produces deterministic chunk IDs, exact 1-indexed start/end lines, and symbol metadata.
"""
import hashlib
import re
from typing import Optional
from ...models.chunk import CodeChunk
from .file_reader import FileReadResult


# Boundary patterns for structural code elements
BOUNDARY_PATTERNS = {
    "Python": re.compile(r"^(?:class|(?:async\s+)?def)\s+([A-Za-z0-9_]+)", re.MULTILINE),
    "JavaScript": re.compile(
        r"^(?:export\s+)?(?:default\s+)?(?:(?:async\s+)?function\s+([A-Za-z0-9_]+)|(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\()",
        re.MULTILINE,
    ),
    "TypeScript": re.compile(
        r"^(?:export\s+)?(?:default\s+)?(?:(?:async\s+)?function\s+([A-Za-z0-9_]+)|(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\(|(?:class|interface|type|enum)\s+([A-Za-z0-9_]+))",
        re.MULTILINE,
    ),
    "Go": re.compile(r"^(?:func\s+(?:\([^\)]+\)\s+)?([A-Za-z0-9_]+)|type\s+([A-Za-z0-9_]+)\s+(?:struct|interface))", re.MULTILINE),
    "Rust": re.compile(r"^(?:pub\s+)?(?:(?:async\s+)?fn\s+([A-Za-z0-9_]+)|(?:struct|enum|trait|impl)\s+([A-Za-z0-9_]+))", re.MULTILINE),
    "Markdown": re.compile(r"^(#{1,3})\s+(.+)", re.MULTILINE),
}


def make_chunk_id(repo_id: str, file_path: str, start_line: int, end_line: int, index: int) -> str:
    """Generates a stable, reproducible chunk ID."""
    token = f"{repo_id}:{file_path}:{start_line}:{end_line}:{index}".encode("utf-8")
    return f"chk_{hashlib.sha256(token).hexdigest()[:16]}"


def find_symbol_name(line: str, language: str) -> Optional[str]:
    """Extracts symbol identifier name from boundary line if present."""
    pattern = BOUNDARY_PATTERNS.get(language)
    if not pattern:
        return None
    match = pattern.search(line)
    if match:
        for group in match.groups():
            if group:
                return group.strip()
    return None


def chunk_file_content(
    repo_id: str,
    file_path: str,
    content: str,
    language: str,
    target_lines: int = 80,
    max_lines: int = 120,
    overlap_lines: int = 15,
) -> list[CodeChunk]:
    """
    Splits source code into bounded, overlapping chunks with exact line numbers.
    Preserves 1-indexed line metadata.
    """
    if not content or not content.strip():
        return []

    lines = content.split("\n")
    total_lines = len(lines)

    # If the file fits within max_lines, return a single complete chunk
    if total_lines <= max_lines:
        first_symbol = None
        for line in lines:
            first_symbol = find_symbol_name(line, language)
            if first_symbol:
                break

        return [
            CodeChunk(
                chunk_id=make_chunk_id(repo_id, file_path, 1, total_lines, 0),
                repo_id=repo_id,
                file_path=file_path,
                language=language,
                start_line=1,
                end_line=total_lines,
                content=content,
                chunk_index=0,
                symbol_name=first_symbol,
                line_count=total_lines,
                char_count=len(content),
            )
        ]

    chunks: list[CodeChunk] = []
    chunk_index = 0
    current_start = 1  # 1-indexed

    while current_start <= total_lines:
        ideal_end = min(total_lines, current_start + target_lines - 1)
        max_end = min(total_lines, current_start + max_lines - 1)

        chosen_end = ideal_end

        # Try snapping to a natural boundary (empty line or symbol definition) between ideal_end and max_end
        if ideal_end < total_lines:
            snap_candidate = -1
            # Look backwards from ideal_end down to (ideal_end - 20) for empty line or symbol
            lookback_floor = max(current_start + 10, ideal_end - 20)
            for l_idx in range(ideal_end, lookback_floor, -1):
                line_text = lines[l_idx - 1]
                if not line_text.strip():  # Empty line is natural boundary
                    snap_candidate = l_idx
                    break
                if find_symbol_name(line_text, language):
                    # Break right before next symbol
                    snap_candidate = l_idx - 1
                    break

            if snap_candidate > current_start:
                chosen_end = snap_candidate
            else:
                chosen_end = ideal_end
        else:
            chosen_end = total_lines

        # Extract chunk lines
        chunk_lines = lines[current_start - 1 : chosen_end]
        chunk_text = "\n".join(chunk_lines)

        # Detect enclosing or top symbol in this chunk
        symbol = None
        for line in chunk_lines:
            symbol = find_symbol_name(line, language)
            if symbol:
                break

        chunk_line_count = chosen_end - current_start + 1
        chunks.append(
            CodeChunk(
                chunk_id=make_chunk_id(repo_id, file_path, current_start, chosen_end, chunk_index),
                repo_id=repo_id,
                file_path=file_path,
                language=language,
                start_line=current_start,
                end_line=chosen_end,
                content=chunk_text,
                chunk_index=chunk_index,
                symbol_name=symbol,
                line_count=chunk_line_count,
                char_count=len(chunk_text),
            )
        )
        chunk_index += 1

        if chosen_end >= total_lines:
            break

        # Calculate next start with overlap
        next_start = chosen_end - overlap_lines + 1
        # Prevent zero or backward progress
        if next_start <= current_start:
            next_start = current_start + 1
        current_start = next_start

    return chunks


def chunk_file_read_result(
    repo_id: str,
    file_result: FileReadResult,
    language: str,
    target_lines: int = 80,
    max_lines: int = 120,
    overlap_lines: int = 15,
) -> list[CodeChunk]:
    """Convenience helper to chunk a FileReadResult directly."""
    if not file_result.is_success or file_result.is_empty:
        return []

    return chunk_file_content(
        repo_id=repo_id,
        file_path=file_result.relative_path,
        content=file_result.content,
        language=language,
        target_lines=target_lines,
        max_lines=max_lines,
        overlap_lines=overlap_lines,
    )
