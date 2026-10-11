"""
Unit tests for Safe ZIP validation and extraction.
Verifies Zip-Slip prevention, malformed handling, and limits enforcement (Step 7).
"""
import io
import sys
import tempfile
import zipfile
from pathlib import Path
import pytest

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.limits import IngestionLimits
from app.services.ingestion.zip_validator import (
    validate_zip_archive,
    safe_extract_zip,
    MalformedZipError,
    ZipSlipError,
    ZipOversizedError,
    ZipSymlinkError,
    ZipBombError,
)


def create_in_memory_zip(entries: dict[str, bytes]) -> bytes:
    """Helper to generate a ZIP archive in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_valid_zip_extraction():
    entries = {
        "src/app.py": b"print('hello world')",
        "src/utils.py": b"def add(a, b): return a + b",
        "README.md": b"# Test Repo",
    }
    zip_bytes = create_in_memory_zip(entries)

    with tempfile.TemporaryDirectory() as tmpdir:
        extract_dir = Path(tmpdir) / "output"
        res, files = safe_extract_zip(zip_bytes, extract_dir)

        assert res.is_valid is True
        assert res.regular_files_count == 3
        assert len(files) == 3

        # Verify files exist on disk inside extract_dir
        for file_path in files:
            assert file_path.exists()
            assert file_path.is_relative_to(extract_dir)

        assert (extract_dir / "src/app.py").read_text() == "print('hello world')"


def test_corrupted_zip_rejected():
    corrupted_data = b"PK\x03\x04not a valid zip file content here definitely corrupt"
    with pytest.raises(MalformedZipError):
        validate_zip_archive(corrupted_data)


def test_zip_slip_dot_dot_rejected():
    # Attempting directory traversal via ../
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil.txt", b"malicious content")
    zip_bytes = buf.getvalue()

    with tempfile.TemporaryDirectory() as tmpdir:
        extract_dir = Path(tmpdir) / "sandbox"
        with pytest.raises(ZipSlipError):
            safe_extract_zip(zip_bytes, extract_dir)

        # Confirm evil.txt was never written
        assert not (Path(tmpdir) / "evil.txt").exists()


def test_zip_slip_absolute_path_rejected():
    # Attempting directory traversal via absolute path
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("/root/evil.txt", b"malicious")
    zip_bytes = buf.getvalue()

    with tempfile.TemporaryDirectory() as tmpdir:
        extract_dir = Path(tmpdir) / "sandbox"
        with pytest.raises(ZipSlipError):
            safe_extract_zip(zip_bytes, extract_dir)


def test_oversized_entry_rejected():
    limits = IngestionLimits(max_file_kb=10)  # 10 KB limit
    large_content = b"A" * (15 * 1024)  # 15 KB
    zip_bytes = create_in_memory_zip({"large.txt": large_content})

    with tempfile.TemporaryDirectory() as tmpdir:
        extract_dir = Path(tmpdir) / "sandbox"
        with pytest.raises(ZipOversizedError):
            safe_extract_zip(zip_bytes, extract_dir, limits=limits)


def test_too_many_entries_rejected():
    limits = IngestionLimits(max_files=5)  # Max 5 files
    entries = {f"file_{i}.txt": b"ok" for i in range(10)}  # 10 entries
    zip_bytes = create_in_memory_zip(entries)

    with tempfile.TemporaryDirectory() as tmpdir:
        extract_dir = Path(tmpdir) / "sandbox"
        with pytest.raises(ZipOversizedError):
            safe_extract_zip(zip_bytes, extract_dir, limits=limits)


def test_oversized_archive_rejected():
    limits = IngestionLimits(max_zip_mb=1)  # 1 MB limit
    # Dummy archive exceeding 1 MB
    large_zip_bytes = b"0" * (2 * 1024 * 1024)
    with pytest.raises(ZipOversizedError):
        validate_zip_archive(large_zip_bytes, limits=limits)


def test_zip_slip_windows_drive_letter_rejected():
    # Attempting directory traversal via drive letter (e.g., C:evil.txt or D:\evil.txt)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("C:evil.txt", b"malicious windows drive traversal")
    zip_bytes = buf.getvalue()

    with tempfile.TemporaryDirectory() as tmpdir:
        extract_dir = Path(tmpdir) / "sandbox"
        with pytest.raises(ZipSlipError):
            safe_extract_zip(zip_bytes, extract_dir)


def test_zip_symlink_rejected():
    # Attempting symlink entry in archive
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        info = zipfile.ZipInfo("symlink_entry")
        info.create_system = 3  # Unix
        info.external_attr = 0o120777 << 16  # S_IFLNK
        zf.writestr(info, "/etc/passwd")
    zip_bytes = buf.getvalue()

    with tempfile.TemporaryDirectory() as tmpdir:
        extract_dir = Path(tmpdir) / "sandbox"
        with pytest.raises(ZipSymlinkError):
            safe_extract_zip(zip_bytes, extract_dir)


def test_zip_slip_nested_traversal_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("sub/deep/../../../evil.txt", b"nested traversal")
    zip_bytes = buf.getvalue()

    with tempfile.TemporaryDirectory() as tmpdir:
        extract_dir = Path(tmpdir) / "sandbox"
        with pytest.raises(ZipSlipError):
            safe_extract_zip(zip_bytes, extract_dir)


def test_zip_slip_windows_backslash_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("..\\windows_traversal.txt", b"backslash traversal")
    zip_bytes = buf.getvalue()

    with tempfile.TemporaryDirectory() as tmpdir:
        extract_dir = Path(tmpdir) / "sandbox"
        with pytest.raises(ZipSlipError):
            safe_extract_zip(zip_bytes, extract_dir)


def test_empty_zip_archive_valid():
    # Empty zip with 0 entries should extract gracefully with 0 files
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        pass
    zip_bytes = buf.getvalue()

    with tempfile.TemporaryDirectory() as tmpdir:
        extract_dir = Path(tmpdir) / "sandbox"
        res, files = safe_extract_zip(zip_bytes, extract_dir)
        assert res.is_valid is True
        assert res.regular_files_count == 0
        assert len(files) == 0
