"""
Pydantic data models for repository ingestion and state.
Ref: PRD Section 6 (FR-01, FR-08, FR-10) and Step 9.
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RepositoryStatus(str, Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class SourceType(str, Enum):
    ZIP = "zip"
    GIT = "git"


class RepositoryStats(BaseModel):
    discovered_files: int = 0
    included_files: int = 0
    skipped_files: int = 0
    skipped_breakdown: dict[str, int] = Field(default_factory=dict)
    languages: dict[str, int] = Field(default_factory=dict)
    total_size_bytes: int = 0


class IngestResponse(BaseModel):
    repo_id: str
    status: RepositoryStatus
    source_type: SourceType
    repo_name: str
    stats: RepositoryStats
    message: str
    error: Optional[str] = None


class RepositorySummary(BaseModel):
    repo_id: str
    name: str
    source_type: SourceType
    status: RepositoryStatus
    created_at: str
    stats: RepositoryStats
