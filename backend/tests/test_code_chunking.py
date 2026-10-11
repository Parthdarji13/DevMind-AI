"""
Unit tests for code chunking and line metadata (Step 14).
Verifies:
- 1-indexed start and end line precision.
- Content extracted matches source lines exactly.
- Chunk ID determinism and stability.
- Syntax-aware symbol detection (Python, TypeScript, Go).
- Overlap continuity across chunks.
"""
import sys
from pathlib import Path
import pytest

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.parser.chunker import (
    chunk_file_content,
    make_chunk_id,
    find_symbol_name,
)


def test_short_file_single_chunk():
    lines = [f"line {i}" for i in range(1, 31)]
    code = "\n".join(lines)

    chunks = chunk_file_content(
        repo_id="repo-1",
        file_path="src/short.py",
        content=code,
        language="Python",
        max_lines=120,
    )

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.start_line == 1
    assert chunk.end_line == 30
    assert chunk.line_count == 30
    assert chunk.content == code
    assert chunk.chunk_index == 0


def test_line_number_fidelity_and_exact_match():
    # Generate 250 lines of code with functions
    code_lines = []
    for i in range(1, 251):
        if i % 30 == 1:
            code_lines.append(f"def function_{i}():")
        elif i % 30 == 2:
            code_lines.append(f"    '''Docstring for function_{i}'''")
        else:
            code_lines.append(f"    x_{i} = {i} * 2")

    full_code = "\n".join(code_lines)

    chunks = chunk_file_content(
        repo_id="repo-test",
        file_path="src/large.py",
        content=full_code,
        language="Python",
        target_lines=60,
        max_lines=90,
        overlap_lines=10,
    )

    assert len(chunks) > 1

    # Verify EVERY chunk's content matches the exact source lines
    for chunk in chunks:
        expected_slice = "\n".join(code_lines[chunk.start_line - 1 : chunk.end_line])
        assert chunk.content == expected_slice
        assert chunk.line_count == (chunk.end_line - chunk.start_line + 1)
        assert chunk.char_count == len(chunk.content)


def test_chunk_id_stability():
    code = "def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n"
    chunks1 = chunk_file_content("repo-1", "math.py", code, "Python")
    chunks2 = chunk_file_content("repo-1", "math.py", code, "Python")

    assert len(chunks1) == len(chunks2)
    for c1, c2 in zip(chunks1, chunks2):
        assert c1.chunk_id == c2.chunk_id
        assert c1.start_line == c2.start_line
        assert c1.end_line == c2.end_line


def test_symbol_extraction():
    assert find_symbol_name("class UserService:", "Python") == "UserService"
    assert find_symbol_name("async def fetch_user_data(user_id: str):", "Python") == "fetch_user_data"
    assert find_symbol_name("export function authenticate() {", "JavaScript") == "authenticate"
    assert find_symbol_name("export const calculateTax = (amount: number) => {", "TypeScript") == "calculateTax"
    assert find_symbol_name("func HandleRequest(w http.ResponseWriter, r *http.Request) {", "Go") == "HandleRequest"
    assert find_symbol_name("x = 10", "Python") is None


def test_overlap_continuity():
    code_lines = [f"line_{i} = {i};" for i in range(1, 180)]
    full_code = "\n".join(code_lines)

    chunks = chunk_file_content(
        repo_id="repo-1",
        file_path="test.ts",
        content=full_code,
        language="TypeScript",
        target_lines=50,
        max_lines=70,
        overlap_lines=15,
    )

    assert len(chunks) >= 3
    # Check overlap: chunk i+1 start_line should be less than chunk i end_line
    for i in range(len(chunks) - 1):
        c_current = chunks[i]
        c_next = chunks[i + 1]
        assert c_next.start_line < c_current.end_line
        assert c_next.start_line > c_current.start_line


def test_empty_content_returns_no_chunks():
    assert chunk_file_content("repo-1", "empty.py", "", "Python") == []
    assert chunk_file_content("repo-1", "blank.py", "   \n\n  ", "Python") == []
