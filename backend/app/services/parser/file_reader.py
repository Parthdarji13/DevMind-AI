"""
Safe source code reading with encoding fallback and failure resilience.
Implements Step 13 of Antigravity guide and FR-04 of PRD v1.2.
Guarantees zero job crashes on empty, malformed, or unreadable files.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

CANDIDATE_ENCODINGS = ("utf-8", "utf-8-sig", "latin-1", "cp1252")


@dataclass(frozen=True)
class FileReadResult:
    relative_path: str
    content: str
    line_count: int
    size_bytes: int
    encoding: str
    is_empty: bool
    is_success: bool
    error_message: Optional[str] = None


def is_binary_stream(chunk: bytes) -> bool:
    """Checks whether byte chunk contains suspicious null bytes indicating binary content."""
    if b"\x00" in chunk:
        return True
    return False


def decode_bytes_safely(raw_bytes: bytes) -> tuple[str, str]:
    """
    Attempts decoding with candidate encodings in priority order.
    Detects and strips UTF-8 BOM cleanly.
    Falls back to utf-8 with error replacement if necessary.
    Returns (decoded_text, used_encoding).
    """
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        try:
            return raw_bytes.decode("utf-8-sig"), "utf-8-sig"
        except UnicodeDecodeError:
            pass

    for enc in CANDIDATE_ENCODINGS:
        try:
            text = raw_bytes.decode(enc)
            return text, enc
        except UnicodeDecodeError:
            continue

    # Resilient fallback: replace invalid bytes
    return raw_bytes.decode("utf-8", errors="replace"), "utf-8-replace"


def read_source_file(
    file_path: Union[Path, str],
    repo_root: Union[Path, str],
    max_file_bytes: int = 500 * 1024,
) -> FileReadResult:
    """
    Safely reads a single source file.
    Preserves repository-relative POSIX path.
    Guarantees no unhandled exceptions crash the job.
    """
    p = Path(file_path).resolve()
    root = Path(repo_root).resolve()

    try:
        rel_path = p.relative_to(root).as_posix()
    except ValueError:
        rel_path = p.name

    if not p.exists():
        return FileReadResult(
            relative_path=rel_path,
            content="",
            line_count=0,
            size_bytes=0,
            encoding="none",
            is_empty=True,
            is_success=False,
            error_message=f"File not found: {p}",
        )

    if not p.is_file():
        return FileReadResult(
            relative_path=rel_path,
            content="",
            line_count=0,
            size_bytes=0,
            encoding="none",
            is_empty=False,
            is_success=False,
            error_message="Target is not a regular file",
        )

    try:
        size = p.stat().st_size
    except OSError as e:
        return FileReadResult(
            relative_path=rel_path,
            content="",
            line_count=0,
            size_bytes=0,
            encoding="none",
            is_empty=False,
            is_success=False,
            error_message=f"Cannot stat file: {str(e)}",
        )

    # Empty file check
    if size == 0:
        return FileReadResult(
            relative_path=rel_path,
            content="",
            line_count=0,
            size_bytes=0,
            encoding="empty",
            is_empty=True,
            is_success=True,
        )

    # Limit check
    if size > max_file_bytes:
        return FileReadResult(
            relative_path=rel_path,
            content="",
            line_count=0,
            size_bytes=size,
            encoding="none",
            is_empty=False,
            is_success=False,
            error_message=f"File size ({size} bytes) exceeds limit ({max_file_bytes} bytes)",
        )

    # Read bytes safely
    try:
        raw_bytes = p.read_bytes()
    except Exception as e:
        return FileReadResult(
            relative_path=rel_path,
            content="",
            line_count=0,
            size_bytes=size,
            encoding="none",
            is_empty=False,
            is_success=False,
            error_message=f"I/O read failure: {str(e)}",
        )

    # Detect hidden binary content
    sample = raw_bytes[:8192]
    if is_binary_stream(sample):
        return FileReadResult(
            relative_path=rel_path,
            content="",
            line_count=0,
            size_bytes=size,
            encoding="binary",
            is_empty=False,
            is_success=False,
            error_message="File contains binary or null byte sequence",
        )

    # Decode safely
    text, used_enc = decode_bytes_safely(raw_bytes)

    # Normalize line endings to LF (\n)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    # If file ends with newline, standard line count
    line_count = len(lines) if normalized else 0

    return FileReadResult(
        relative_path=rel_path,
        content=normalized,
        line_count=line_count,
        size_bytes=size,
        encoding=used_enc,
        is_empty=False,
        is_success=True,
    )


def batch_read_repository_files(
    repo_root: Union[Path, str],
    relative_paths: list[str],
    max_file_bytes: int = 500 * 1024,
) -> tuple[list[FileReadResult], list[FileReadResult]]:
    """
    Reads multiple repository files in batch.
    Segregates results into (successful_reads, failed_reads).
    """
    root = Path(repo_root).resolve()
    successful: list[FileReadResult] = []
    failed: list[FileReadResult] = []

    for rel_path in relative_paths:
        full_path = root / rel_path
        res = read_source_file(full_path, repo_root=root, max_file_bytes=max_file_bytes)
        if res.is_success and not res.is_empty:
            successful.append(res)
        elif not res.is_success:
            failed.append(res)
        # Empty files can be tracked or skipped cleanly without failure

    return successful, failed
