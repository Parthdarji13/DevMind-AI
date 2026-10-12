"""
Repository Management API endpoints for DevMind AI.
Provides per-user repository listing, on-demand re-indexing, and clean deletion.
Ref: PRD Section 9, 10; Security & Repositories Architecture.
"""
import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel

from ..models.repository import RepositoryStatus, RepositorySummary
from ..services.auth.jwt_handler import UserContext, get_current_user
from ..services.ingestion.repository_manager import repo_manager
from ..services.indexing.pipeline import run_repository_indexing

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repositories", tags=["repositories"])


class DeleteResponse(BaseModel):
    status: str
    repo_id: str
    message: str


class ReindexResponse(BaseModel):
    status: str
    repo_id: str
    message: str


@router.get("", response_model=list[RepositorySummary])
def list_user_repositories(user: UserContext = Depends(get_current_user)):
    """
    Returns all repositories owned by the current authenticated user.
    Enforces per-user privacy isolation.
    """
    return repo_manager.list_repositories(owner_id=user.id)


@router.delete("/{repo_id}", response_model=DeleteResponse)
def delete_repository(
    repo_id: str,
    user: UserContext = Depends(get_current_user),
):
    """
    Completely removes a repository, its extracted source files,
    its BM25 indices, and vector embeddings from disk storage.
    """
    repo = repo_manager.get_repository(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repo_id}' not found.",
        )

    # Enforce ownership check unless it is an unassigned legacy repo
    if repo.owner_id and repo.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this repository.",
        )

    repo_name = repo.name
    repo_manager.cleanup_repository(repo_id)
    logger.info(f"Repository '{repo_name}' ({repo_id}) deleted by user '{user.id}'.")

    return DeleteResponse(
        status="deleted",
        repo_id=repo_id,
        message=f"Repository '{repo_name}' and all associated index data have been completely deleted.",
    )


@router.post("/{repo_id}/reindex", response_model=ReindexResponse)
def reindex_repository(
    repo_id: str,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
):
    """
    Triggers on-demand re-indexing of an existing repository.
    Re-scans files, re-chunks, and re-computes dense/lexical representations.
    """
    repo = repo_manager.get_repository(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repo_id}' not found.",
        )

    if repo.owner_id and repo.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to re-index this repository.",
        )

    repo_dir = repo_manager.get_repo_dir(repo_id)
    if not repo_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository source directory not found on disk. Cannot re-index.",
        )

    repo_manager.update_status(repo_id, RepositoryStatus.PROCESSING)
    background_tasks.add_task(run_repository_indexing, repo_id)

    return ReindexResponse(
        status="processing",
        repo_id=repo_id,
        message="Re-indexing started in background.",
    )
