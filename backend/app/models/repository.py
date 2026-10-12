"""
Pydantic data models for repository ingestion, state, metrics, and progress.
Ref: PRD Section 6 (FR-08, FR-10), Section 11, Section 17.5; Step 12.
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


class StageStatus(str, Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class StageDetail(BaseModel):
    step_number: int
    name: str
    status: StageStatus = StageStatus.WAITING
    detail: str = ""
    current_count: Optional[int] = None
    total_count: Optional[int] = None


class IngestionMetrics(BaseModel):
    discovered_files: int = 0
    included_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0
    indexed_files: int = 0
    total_lines: int = 0
    duration_seconds: float = 0.0


class RepositoryStats(BaseModel):
    discovered_files: int = 0
    included_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0
    indexed_files: int = 0
    skipped_breakdown: dict[str, int] = Field(default_factory=dict)
    languages: dict[str, int] = Field(default_factory=dict)
    total_size_bytes: int = 0
    total_lines: int = 0
    duration_seconds: float = 0.0


class IngestionProgress(BaseModel):
    repo_id: str
    repo_name: str
    source_type: SourceType
    overall_status: RepositoryStatus
    current_step: int = 1
    percentage: int = 0
    stages: list[StageDetail] = Field(default_factory=list)
    metrics: IngestionMetrics = Field(default_factory=IngestionMetrics)
    skipped_breakdown: dict[str, int] = Field(default_factory=dict)
    languages: dict[str, int] = Field(default_factory=dict)
    error_message: Optional[str] = None

    def reconcile_counters(self) -> bool:
        """
        Verifies mathematical reconciliation of counters.
        Total discovered must equal included + skipped.
        """
        return self.metrics.discovered_files == (
            self.metrics.included_files + self.metrics.skipped_files
        )


class IngestResponse(BaseModel):
    repo_id: str
    status: RepositoryStatus
    source_type: SourceType
    repo_name: str
    stats: RepositoryStats
    message: str
    error: Optional[str] = None
    owner_id: Optional[str] = None


class RepositorySummary(BaseModel):
    repo_id: str
    name: str
    source_type: SourceType
    status: RepositoryStatus
    created_at: str
    stats: RepositoryStats
    progress: Optional[IngestionProgress] = None
    owner_id: Optional[str] = None



class IngestGitRequest(BaseModel):
    url: str
