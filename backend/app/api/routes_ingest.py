"""
Ingestion API routes for ZIP uploads and repository management.
Ref: PRD Section 6 (FR-01, FR-08), Section 17.4; Step 9 of execution guide.
"""
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile, status
from ..core.config import get_settings
from ..models.repository import (
    IngestResponse,
    IngestGitRequest,
    RepositoryStats,
    RepositoryStatus,
    RepositorySummary,
    SourceType,
    IngestionProgress,
)
from ..services.ingestion.zip_validator import (
    safe_extract_zip,
    MalformedZipError,
    ZipSlipError,
    ZipOversizedError,
    ZipBombError,
    ZipSymlinkError,
)
from ..services.ingestion.git_validator import (
    validate_git_url,
    GitValidationError,
)
from ..services.ingestion.git_cloner import (
    clone_and_filter_public_repo,
    GitCloneError,
    GitTimeoutError,
)
from ..services.ingestion.progress_tracker import ProgressTracker
from ..services.filtering.scanner import scan_and_filter_repository
from ..services.ingestion.repository_manager import repo_manager
from ..services.indexing.pipeline import run_repository_indexing

router = APIRouter(prefix="/api/ingest", tags=["Ingestion"])
settings = get_settings()


@router.post(
    "/zip",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a repository ZIP archive",
)
async def upload_zip_repository(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    # 1. Filename validation
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a valid .zip archive.",
        )

    # 2. Bounded stream reading to enforce max size without allocating unbounded memory (Problem 4)
    max_bytes = settings.limits.max_zip_bytes
    if hasattr(file, "size") and file.size is not None and file.size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Archive size exceeds maximum allowed limit of {settings.limits.max_zip_mb} MB.",
        )

    chunks: list[bytes] = []
    total_bytes = 0
    chunk_size = 1024 * 1024  # 1MB chunks
    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                del chunks
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Archive size exceeds maximum allowed limit of {settings.limits.max_zip_mb} MB.",
                )
            chunks.append(chunk)
        content = b"".join(chunks)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded archive file.",
        )

    # 3. Double-check archive size
    if not settings.limits.validate_archive_size(len(content)):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Archive size exceeds maximum allowed limit of {settings.limits.max_zip_mb} MB.",
        )

    # 4. Create isolated repository tracking
    repo = repo_manager.create_repository(
        name=file.filename,
        source_type=SourceType.ZIP,
    )
    extract_dir = repo_manager.get_repo_dir(repo.repo_id)

    # 5. Safe extraction with security protections
    try:
        validation_res, extracted_files = safe_extract_zip(
            source=content,
            target_extract_dir=extract_dir,
            limits=settings.limits,
        )
        if repo.progress:
            ProgressTracker.complete_stage(
                repo.progress,
                1,
                f"Extracted archive: {validation_res.regular_files_count} files",
            )
    except ZipSlipError as e:
        if repo.progress:
            ProgressTracker.fail(repo.progress, 1, f"Zip-Slip security error: {str(e)}")
        repo_manager.cleanup_repository(repo.repo_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security violation (Zip-Slip): {str(e)}",
        )
    except MalformedZipError as e:
        if repo.progress:
            ProgressTracker.fail(repo.progress, 1, f"Malformed archive: {str(e)}")
        repo_manager.cleanup_repository(repo.repo_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed or corrupt ZIP archive: {str(e)}",
        )
    except ZipOversizedError as e:
        if repo.progress:
            ProgressTracker.fail(repo.progress, 1, f"Limit exceeded: {str(e)}")
        repo_manager.cleanup_repository(repo.repo_id)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Repository limit exceeded: {str(e)}",
        )
    except (ZipBombError, ZipSymlinkError) as e:
        if repo.progress:
            ProgressTracker.fail(repo.progress, 1, f"Security violation: {str(e)}")
        repo_manager.cleanup_repository(repo.repo_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security violation in archive: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Unexpected error extracting archive: {e}", exc_info=True)
        if repo.progress:
            ProgressTracker.fail(repo.progress, 1, "An unexpected extraction error occurred.")
        repo_manager.cleanup_repository(repo.repo_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred while extracting the archive.",
        )

    # 6. Scan and filter files
    filter_report = scan_and_filter_repository(extract_dir, limits=settings.limits)

    if filter_report.total_included == 0:
        if repo.progress:
            ProgressTracker.fail(repo.progress, 2, "No supported source files found.")
        repo_manager.cleanup_repository(repo.repo_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No supported source code or text files found in the archive.",
        )

    if repo.progress:
        ProgressTracker.complete_stage(
            repo.progress,
            2,
            f"Filtered: {filter_report.total_included} included, {filter_report.total_skipped} skipped",
        )
        ProgressTracker.set_metrics(
            repo.progress,
            discovered=filter_report.total_discovered,
            included=filter_report.total_included,
            skipped=filter_report.total_skipped,
            skipped_breakdown=filter_report.skipped_breakdown,
            languages=filter_report.language_breakdown,
        )

    # 7. Update repository stats and state
    stats = RepositoryStats(
        discovered_files=filter_report.total_discovered,
        included_files=filter_report.total_included,
        skipped_files=filter_report.total_skipped,
        skipped_breakdown=filter_report.skipped_breakdown,
        languages=filter_report.language_breakdown,
        total_size_bytes=filter_report.total_included_bytes,
    )

    repo_manager.update_status(
        repo_id=repo.repo_id,
        status=RepositoryStatus.PROCESSING,
        stats=stats,
    )

    # Enqueue background indexing pipeline (Stages 3 -> 4 -> 5)
    background_tasks.add_task(run_repository_indexing, repo.repo_id)

    return IngestResponse(
        repo_id=repo.repo_id,
        status=RepositoryStatus.PROCESSING,
        source_type=SourceType.ZIP,
        repo_name=file.filename,
        stats=stats,
        message="Repository uploaded, extracted, and queued for background indexing.",
    )


@router.post(
    "/git",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a public Git repository via URL",
)
async def ingest_git_repository(
    req: IngestGitRequest,
    background_tasks: BackgroundTasks,
):
    # 1. Validate URL & SSRF
    try:
        validation = validate_git_url(req.url)
    except GitValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Git URL: {str(e)}",
        )

    # 2. Create isolated repository record
    repo = repo_manager.create_repository(
        name=validation.repo_name,
        source_type=SourceType.GIT,
    )
    target_dir = repo_manager.get_repo_dir(repo.repo_id)

    # 3. Clone and filter with controlled timeout & limits
    try:
        val_res, filter_report = clone_and_filter_public_repo(
            raw_url=req.url,
            target_dir=target_dir,
            limits=settings.limits,
            resolve_dns=True,
        )
        if repo.progress:
            ProgressTracker.complete_stage(
                repo.progress,
                1,
                f"Cloned public repository '{validation.repo_name}'",
            )
            ProgressTracker.complete_stage(
                repo.progress,
                2,
                f"Filtered: {filter_report.total_included} included, {filter_report.total_skipped} skipped",
            )
            ProgressTracker.set_metrics(
                repo.progress,
                discovered=filter_report.total_discovered,
                included=filter_report.total_included,
                skipped=filter_report.total_skipped,
                skipped_breakdown=filter_report.skipped_breakdown,
                languages=filter_report.language_breakdown,
            )
    except GitTimeoutError as e:
        if repo.progress:
            ProgressTracker.fail(repo.progress, 1, f"Timeout: {str(e)}")
        repo_manager.cleanup_repository(repo.repo_id)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(e),
        )
    except GitCloneError as e:
        if repo.progress:
            ProgressTracker.fail(repo.progress, 1, f"Clone error: {str(e)}")
        repo_manager.cleanup_repository(repo.repo_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error ingesting Git repository: {e}", exc_info=True)
        if repo.progress:
            ProgressTracker.fail(repo.progress, 1, "An unexpected git ingestion error occurred.")
        repo_manager.cleanup_repository(repo.repo_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred while processing the Git repository.",
        )

    # 4. Update repository stats and state
    stats = RepositoryStats(
        discovered_files=filter_report.total_discovered,
        included_files=filter_report.total_included,
        skipped_files=filter_report.total_skipped,
        skipped_breakdown=filter_report.skipped_breakdown,
        languages=filter_report.language_breakdown,
        total_size_bytes=filter_report.total_included_bytes,
    )

    repo_manager.update_status(
        repo_id=repo.repo_id,
        status=RepositoryStatus.PROCESSING,
        stats=stats,
    )

    # Enqueue background indexing pipeline (Stages 3 -> 4 -> 5)
    background_tasks.add_task(run_repository_indexing, repo.repo_id)

    return IngestResponse(
        repo_id=repo.repo_id,
        status=RepositoryStatus.PROCESSING,
        source_type=SourceType.GIT,
        repo_name=validation.repo_name,
        stats=stats,
        message="Public Git repository cloned, filtered, and queued for background indexing.",
    )


@router.post(
    "/index/{repo_id}",
    summary="Trigger or retry background indexing for an ingested repository",
)
def trigger_repository_indexing(
    repo_id: str,
    background_tasks: BackgroundTasks,
):
    repo = repo_manager.get_repository(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repo_id}' not found.",
        )
    background_tasks.add_task(run_repository_indexing, repo_id)
    return {"status": "indexing_started", "repo_id": repo_id}


@router.get(
    "/progress/{repo_id}",
    response_model=IngestionProgress,
    summary="Get granular 5-stage ingestion progress and reconciled counters",
)
def get_ingestion_progress(repo_id: str):
    repo = repo_manager.get_repository(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repo_id}' not found.",
        )
    if not repo.progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Progress tracking not found for repository '{repo_id}'.",
        )
    return repo.progress


@router.get(
    "/status/{repo_id}",
    response_model=RepositorySummary,
    summary="Get repository ingestion and processing status",
)
def get_repository_status(repo_id: str):
    repo = repo_manager.get_repository(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repo_id}' not found.",
        )
    return repo


@router.get(
    "/list",
    response_model=list[RepositorySummary],
    summary="List all indexed repositories (Local workspace instances only)",
)
def list_repositories(request: Request):
    # Protect privacy: restrict listing to local loopback workspace instances
    client_host = request.client.host if request.client else "127.0.0.1"
    if client_host not in ("127.0.0.1", "localhost", "::1", "testclient"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Repository listing is restricted to local workspace instances.",
        )
    return repo_manager.list_repositories()
