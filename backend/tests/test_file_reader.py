"""
Unit tests for Safe Source File Reading (Step 13).
Verifies encoding fallbacks, path preservation, empty/corrupt handling, and resilience.
"""
import sys
import tempfile
from pathlib import Path
import pytest

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.parser.file_reader import (
    read_source_file,
    batch_read_repository_files,
    FileReadResult,
)


def test_read_utf8_source_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        sub = root / "src"
        sub.mkdir()
        code_file = sub / "app.py"
        code_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

        res = read_source_file(code_file, repo_root=root)
        assert res.is_success is True
        assert res.relative_path == "src/app.py"
        assert res.line_count == 3
        assert "def hello():" in res.content
        assert res.encoding == "utf-8"


def test_read_utf8_with_bom():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        file_path = root / "config.json"
        # Write bytes with UTF-8 BOM
        bom_bytes = b"\xef\xbb\xbf{\n  \"version\": 1\n}\n"
        file_path.write_bytes(bom_bytes)

        res = read_source_file(file_path, repo_root=root)
        assert res.is_success is True
        assert res.relative_path == "config.json"
        assert res.content.startswith("{\n")  # BOM stripped cleanly
        assert res.encoding == "utf-8-sig"


def test_read_latin1_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        file_path = root / "legacy.txt"
        # Write bytes containing Latin-1 specific character (e.g. copyright sign \xa9 or accented \xe9)
        latin1_bytes = b"# Copyright \xa9 2026\n# Caf\xe9 project\n"
        file_path.write_bytes(latin1_bytes)

        res = read_source_file(file_path, repo_root=root)
        assert res.is_success is True
        assert "Copyright" in res.content
        assert res.line_count == 3


def test_read_empty_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        file_path = root / "__init__.py"
        file_path.write_bytes(b"")

        res = read_source_file(file_path, repo_root=root)
        assert res.is_success is True
        assert res.is_empty is True
        assert res.content == ""
        assert res.line_count == 0


def test_binary_null_bytes_rejected_gracefully():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        file_path = root / "fake_script.py"
        # Has .py extension but contains binary null bytes
        file_path.write_bytes(b"\x7fELF\x01\x00\x00\x00\x00\x00\x00")

        res = read_source_file(file_path, repo_root=root)
        assert res.is_success is False
        assert "binary" in res.error_message.lower()


def test_oversized_file_rejected_gracefully():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        file_path = root / "giant.txt"
        file_path.write_bytes(b"A" * 2000)

        # Set limit to 1000 bytes
        res = read_source_file(file_path, repo_root=root, max_file_bytes=1000)
        assert res.is_success is False
        assert "exceeds limit" in res.error_message.lower()


def test_nonexistent_file_rejected_gracefully():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        res = read_source_file(root / "missing.py", repo_root=root)
        assert res.is_success is False
        assert "not found" in res.error_message.lower()


def test_batch_read_segregation():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "ok1.py").write_text("x = 1\n", encoding="utf-8")
        (root / "ok2.ts").write_text("const y = 2;\n", encoding="utf-8")
        (root / "empty.py").write_bytes(b"")
        (root / "corrupt_bin.py").write_bytes(b"bad\x00data")

        files = ["ok1.py", "ok2.ts", "empty.py", "corrupt_bin.py", "missing.py"]
        success, failed = batch_read_repository_files(root, files)

        assert len(success) == 2
        assert {s.relative_path for s in success} == {"ok1.py", "ok2.ts"}
        assert len(failed) == 2  # corrupt_bin.py and missing.py
        failed_paths = {f.relative_path for f in failed}
        assert "corrupt_bin.py" in failed_paths
        assert "missing.py" in failed_paths
