"""
Ingestion progress tracker and metrics reconciliation engine.
Ref: PRD Section 17.5; Step 12 of execution guide.
Tracks the 5 standard ingestion stages and ensures counters strictly reconcile.
"""
import time
from typing import Optional
from ...models.repository import (
    IngestionProgress,
    IngestionMetrics,
    StageDetail,
    StageStatus,
    RepositoryStatus,
    SourceType,
)

STAGE_DEFINITIONS = [
    (1, "Fetched repository", "Fetch and extract source archive or clone repository"),
    (2, "Filtered files", "Filter dependency, build, binary, and secret files"),
    (3, "Chunking code", "Parse source code and generate syntax-bounded chunks"),
    (4, "Building search index", "Compute vectors and construct persistent search index"),
    (5, "Ready for questions", "Repository is ready for evidence-grounded Q&A"),
]


class ProgressTracker:
    """Manages real-time stage transitions, percentages, and counter reconciliation."""

    @staticmethod
    def initialize_progress(
        repo_id: str,
        repo_name: str,
        source_type: SourceType,
    ) -> IngestionProgress:
        stages = [
            StageDetail(
                step_number=step,
                name=name,
                status=StageStatus.WAITING,
                detail=desc,
            )
            for step, name, desc in STAGE_DEFINITIONS
        ]

        # Stage 1 starts in progress
        stages[0].status = StageStatus.IN_PROGRESS
        stages[0].detail = "Fetching repository source..."

        return IngestionProgress(
            repo_id=repo_id,
            repo_name=repo_name,
            source_type=source_type,
            overall_status=RepositoryStatus.PROCESSING,
            current_step=1,
            percentage=0,
            stages=stages,
            metrics=IngestionMetrics(),
        )

    @staticmethod
    def advance_to_stage(
        progress: IngestionProgress,
        step_number: int,
        status: StageStatus = StageStatus.IN_PROGRESS,
        detail: str = "",
        current_count: Optional[int] = None,
        total_count: Optional[int] = None,
    ) -> None:
        """Updates a specific stage and recalculates real progress percentage."""
        if not (1 <= step_number <= 5):
            raise ValueError(f"Step number must be between 1 and 5 (got {step_number}).")

        progress.current_step = step_number
        idx = step_number - 1
        progress.stages[idx].status = status
        if detail:
            progress.stages[idx].detail = detail
        if current_count is not None:
            progress.stages[idx].current_count = current_count
        if total_count is not None:
            progress.stages[idx].total_count = total_count

        # Mark all prior steps as done
        for i in range(idx):
            if progress.stages[i].status != StageStatus.DONE:
                progress.stages[i].status = StageStatus.DONE

        # Compute accurate percentage based on completed and in-progress stages
        # Each step represents 20%
        completed_steps = sum(1 for s in progress.stages if s.status == StageStatus.DONE)
        base_percentage = completed_steps * 20

        # Sub-percentage for in-progress step
        sub_percentage = 0
        if status == StageStatus.IN_PROGRESS and current_count and total_count and total_count > 0:
            fraction = min(1.0, current_count / total_count)
            sub_percentage = int(fraction * 20)

        progress.percentage = min(100, base_percentage + sub_percentage)

        if progress.stages[-1].status == StageStatus.DONE:
            progress.overall_status = RepositoryStatus.READY
            progress.percentage = 100

    @staticmethod
    def complete_stage(
        progress: IngestionProgress,
        step_number: int,
        detail: str = "Done",
    ) -> None:
        idx = step_number - 1
        progress.stages[idx].status = StageStatus.DONE
        progress.stages[idx].detail = detail
        if progress.stages[idx].total_count is not None:
            progress.stages[idx].current_count = progress.stages[idx].total_count
        completed = sum(1 for s in progress.stages if s.status == StageStatus.DONE)
        progress.percentage = completed * 20
        if step_number < 5:
            progress.current_step = step_number + 1
            progress.stages[step_number].status = StageStatus.IN_PROGRESS
        else:
            progress.overall_status = RepositoryStatus.READY
            progress.percentage = 100

    @staticmethod
    def set_metrics(
        progress: IngestionProgress,
        discovered: int,
        included: int,
        skipped: int,
        failed: int = 0,
        indexed: int = 0,
        total_lines: int = 0,
        duration_seconds: float = 0.0,
        skipped_breakdown: Optional[dict[str, int]] = None,
        languages: Optional[dict[str, int]] = None,
    ) -> bool:
        """Sets metrics and verifies strict reconciliation."""
        metrics = IngestionMetrics(
            discovered_files=discovered,
            included_files=included,
            skipped_files=skipped,
            failed_files=failed,
            indexed_files=indexed,
            total_lines=total_lines,
            duration_seconds=duration_seconds,
        )
        progress.metrics = metrics
        if skipped_breakdown:
            progress.skipped_breakdown = skipped_breakdown
        if languages:
            progress.languages = languages

        # Reconcile counters: discovered MUST equal included + skipped
        return progress.reconcile_counters()

    @staticmethod
    def fail(
        progress: IngestionProgress,
        step_number: int,
        error_message: str,
    ) -> None:
        progress.overall_status = RepositoryStatus.FAILED
        progress.error_message = error_message
        idx = min(4, max(0, step_number - 1))
        progress.stages[idx].status = StageStatus.FAILED
        progress.stages[idx].detail = error_message
