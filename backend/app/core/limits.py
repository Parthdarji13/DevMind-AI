"""
Configurable limits for DevMind AI repository ingestion and processing.
Ref: PRD v1.2 Sections 10, 17.4, 17.10
"""
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class IngestionLimits:
    max_zip_mb: int = int(os.getenv("MAX_ZIP_MB", "100"))
    max_files: int = int(os.getenv("MAX_FILES", "3000"))
    max_file_kb: int = int(os.getenv("MAX_FILE_KB", "1000"))
    retention_days: int = int(os.getenv("RETENTION_DAYS", "7"))
    git_clone_timeout_seconds: int = int(os.getenv("GIT_CLONE_TIMEOUT_SECONDS", "60"))

    @property
    def max_zip_bytes(self) -> int:
        return self.max_zip_mb * 1024 * 1024

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_kb * 1024

    def validate_file_size(self, size_bytes: int) -> bool:
        return size_bytes <= self.max_file_bytes

    def validate_archive_size(self, size_bytes: int) -> bool:
        return size_bytes <= self.max_zip_bytes

    def validate_file_count(self, count: int) -> bool:
        return count <= self.max_files


DEFAULT_LIMITS = IngestionLimits()
