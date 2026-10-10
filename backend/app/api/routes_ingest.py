"""
Ingestion API routes for ZIP uploads and repository management.
Ref: PRD Section 6 (FR-01, FR-08), Section 17.4; Step 9 of execution guide.
"""
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from ..core.config import get_settings
from ..models.repository import (
    IngestResponse,
    RepositoryStats,
    RepositoryStatus,
    RepositorySummary,
    SourceType,
)
from ..services.ingestion.zip_validator import (
    safe_extract_zip,
    MalformedZipError,
    ZipSlipError,
    ZipOversizedError,
    ZipBombError,
    ZipSymlinkError,
)
from ..services.filtering.scanner import scan_and_filter_repository
from ..services.ingestion.repository_manager import repo_manager

router = APIRouter(prefix="/api/ingest", tags=["Ingestion"])
settings = get_settings()


@router.post(
    "/zip",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a repository ZIP archive",
)
async def upload_zip_repository(file: UploadFile = File(...)):
    # 1. Filename validation
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a valid .zip archive.",
        )

    # 2. Read archive content into memory safely
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {str(e)}",
        )

    # 3. Size check before creating repo
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
    except ZipSlipError as e:
        repo_manager.cleanup_repository(repo.repo_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security violation (Zip-Slip): {str(e)}",
        )
    except MalformedZipError as e:
        repo_manager.cleanup_repository(repo.repo_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed or corrupt ZIP archive: {str(e)}",
        )
    except ZipOversizedError as e:
        repo_manager.cleanup_repository(repo.repo_id)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Repository limit exceeded: {str(e)}",
        )
    except (ZipBombError, ZipSymlinkError) as e:
        repo_manager.cleanup_repository(repo.repo_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security violation in archive: {str(e)}",
        )
    except Exception as e:
        repo_manager.cleanup_repository(repo.repo_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error extracting archive: {str(e)}",
        )

    # 6. Scan and filter files
    filter_report = scan_and_filter_repository(extract_dir, limits=settings.limits)

    if filter_report.total_included == 0:
        repo_manager.cleanup_repository(repo.repo_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No supported source code or text files found in the archive.",
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
        status=RepositoryStatus.READY,
        stats=stats,
    )

    return IngestResponse(
        repo_id=repo.repo_id,
        status=RepositoryStatus.READY,
        source_type=SourceType.ZIP,
        repo_name=file.filename,
        stats=stats,
        message="Repository uploaded, extracted, and filtered successfully.",
    )


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
    summary="List all indexed repositories",
)
def list_repositories():
    return repo_manager.list_repositories()
