"""
Safe ZIP archive validation and extraction for DevMind AI.
Prevents Zip-Slip, path traversal, symlink hijacking, and decompression bombs.
Ref: PRD Section 10, Step 7 of execution guide.
"""
from dataclasses import dataclass
import io
import os
from pathlib import Path, PurePath
import stat
import zipfile
from typing import BinaryIO, Union
from ...core.limits import IngestionLimits, DEFAULT_LIMITS


class ZipValidationError(Exception):
    """Base error for ZIP validation failures."""
    pass


class MalformedZipError(ZipValidationError):
    """Raised when the file is corrupt or not a valid ZIP archive."""
    pass


class ZipSlipError(ZipValidationError):
    """Raised when an entry attempts directory traversal outside target workspace."""
    pass


class ZipOversizedError(ZipValidationError):
    """Raised when the archive, file count, or entry size exceeds configured limits."""
    pass


class ZipBombError(ZipValidationError):
    """Raised when compression ratio or expanded size indicates a zip bomb."""
    pass


class ZipSymlinkError(ZipValidationError):
    """Raised when an archive contains symlinks that could escape boundaries."""
    pass


@dataclass
class ZipValidationResult:
    is_valid: bool
    total_entries: int
    regular_files_count: int
    total_uncompressed_bytes: int
    archive_size_bytes: int


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    """Checks if zip entry has Unix symlink attributes."""
    mode = info.external_attr >> 16
    return stat.S_ISLNK(mode) != 0


def _is_safe_relative_path(member_name: str, target_dir: Path) -> bool:
    """
    Checks that member_name does not traverse outside target_dir.
    Guards against: ../, leading /, drive letters (C:), and null bytes.
    """
    if "\0" in member_name:
        return False

    # Normalize slashes
    clean_name = member_name.replace("\\", "/").strip()
    if not clean_name:
        return False

    # Disallow absolute paths or Windows drive letters
    p = PurePath(clean_name)
    if p.is_absolute() or clean_name.startswith("/") or clean_name.startswith("\\"):
        return False

    # Check for drive colon (e.g. C:foo)
    if ":" in clean_name:
        return False

    # Resolve candidate target
    try:
        resolved_target = (target_dir / clean_name).resolve()
        target_dir_resolved = target_dir.resolve()
        # Ensure resolved candidate is strictly within target directory
        return resolved_target.is_relative_to(target_dir_resolved)
    except (ValueError, RuntimeError):
        return False


def validate_zip_archive(
    source: Union[bytes, BinaryIO, Path, str],
    limits: IngestionLimits = DEFAULT_LIMITS,
    target_extract_dir: Union[Path, str] = Path("."),
) -> tuple[zipfile.ZipFile, ZipValidationResult]:
    """
    Validates a ZIP archive without writing files to disk.
    Raises specific ZipValidationError subclasses on any violation.
    """
    extract_dir = Path(target_extract_dir).resolve()

    # Determine archive size
    if isinstance(source, bytes):
        archive_size = len(source)
        file_obj = io.BytesIO(source)
    elif isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists() or not p.is_file():
            raise MalformedZipError(f"ZIP file not found at {p}")
        archive_size = p.stat().st_size
        file_obj = open(p, "rb")
    else:
        # File-like object
        current_pos = source.tell()
        source.seek(0, os.SEEK_END)
        archive_size = source.tell()
        source.seek(current_pos, os.SEEK_SET)
        file_obj = source

    # 1. Enforce maximum archive upload size
    if not limits.validate_archive_size(archive_size):
        raise ZipOversizedError(
            f"Archive size ({archive_size / (1024 * 1024):.2f} MB) exceeds maximum allowed limit ({limits.max_zip_mb} MB)."
        )

    # 2. Check zip validity
    try:
        zf = zipfile.ZipFile(file_obj, "r")
    except zipfile.BadZipFile as e:
        raise MalformedZipError(f"Corrupt or invalid ZIP archive: {str(e)}") from e
    except Exception as e:
        raise MalformedZipError(f"Unable to read ZIP archive: {str(e)}") from e

    entries = zf.infolist()
    total_entries = len(entries)

    # 3. Check total entry count
    if not limits.validate_file_count(total_entries):
        raise ZipOversizedError(
            f"Archive contains {total_entries} entries, which exceeds the limit of {limits.max_files} files."
        )

    regular_files = 0
    total_uncompressed = 0
    max_total_uncompressed_bytes = limits.max_zip_bytes * 10  # max 10x expansion allowance

    for info in entries:
        filename = info.filename

        # Ignore empty entries
        if not filename or filename.endswith("/"):
            continue

        # 4. Check for Zip-Slip / Path Traversal
        if not _is_safe_relative_path(filename, extract_dir):
            raise ZipSlipError(
                f"Zip-Slip detected: entry '{filename}' attempts directory traversal outside destination."
            )

        # 5. Check for symlinks
        if _is_symlink(info):
            raise ZipSymlinkError(
                f"Unsafe symlink entry detected: '{filename}'. Symlinks in archives are rejected for security."
            )

        # 6. Check per-file uncompressed size
        if info.file_size > limits.max_file_bytes:
            raise ZipOversizedError(
                f"Entry '{filename}' uncompressed size ({info.file_size / 1024:.1f} KB) exceeds per-file limit ({limits.max_file_kb} KB)."
            )

        # 7. Check zip bomb expansion ratio per file
        if info.compress_size > 0:
            ratio = info.file_size / info.compress_size
            if ratio > 100 and info.file_size > 1024 * 100:  # > 100:1 ratio and > 100KB
                raise ZipBombError(
                    f"Possible zip bomb detected in '{filename}' (compression ratio {ratio:.1f}:1)."
                )

        regular_files += 1
        total_uncompressed += info.file_size

        if total_uncompressed > max_total_uncompressed_bytes:
            raise ZipBombError(
                f"Total uncompressed archive size exceeds maximum safe ceiling ({max_total_uncompressed_bytes / (1024 * 1024):.1f} MB)."
            )

    result = ZipValidationResult(
        is_valid=True,
        total_entries=total_entries,
        regular_files_count=regular_files,
        total_uncompressed_bytes=total_uncompressed,
        archive_size_bytes=archive_size,
    )
    return zf, result


def safe_extract_zip(
    source: Union[bytes, BinaryIO, Path, str],
    target_extract_dir: Union[Path, str],
    limits: IngestionLimits = DEFAULT_LIMITS,
) -> tuple[ZipValidationResult, list[Path]]:
    """
    Validates and extracts all regular files safely into target_extract_dir.
    Guarantees zero files extracted outside target_extract_dir.
    Returns (ZipValidationResult, list of extracted file Paths).
    """
    extract_dir = Path(target_extract_dir).resolve()
    extract_dir.mkdir(parents=True, exist_ok=True)

    zf, validation_result = validate_zip_archive(
        source=source,
        limits=limits,
        target_extract_dir=extract_dir,
    )

    extracted_files: list[Path] = []

    try:
        for info in zf.infolist():
            if info.filename.endswith("/"):
                continue

            # Double check boundary
            dest_path = (extract_dir / info.filename).resolve()
            if not dest_path.is_relative_to(extract_dir):
                raise ZipSlipError(f"Illegal extraction destination: {dest_path}")

            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Extract in bounded chunks
            with zf.open(info) as src_f, open(dest_path, "wb") as dst_f:
                bytes_written = 0
                while chunk := src_f.read(65536):
                    bytes_written += len(chunk)
                    if bytes_written > limits.max_file_bytes:
                        # Clean up partial file
                        dst_f.close()
                        if dest_path.exists():
                            dest_path.unlink()
                        raise ZipOversizedError(f"Entry {info.filename} exceeded maximum size during extraction.")
                    dst_f.write(chunk)

            extracted_files.append(dest_path)

        return validation_result, extracted_files
    finally:
        zf.close()
