"""
Access control service for DevMind AI.
Enforces multi-tenant repository authorization and prevents unauthorized cross-tenant operations.
Ref: PRD Section 17 & Security Architecture.
"""
import logging
from typing import Optional
from fastapi import HTTPException, status

from .jwt_handler import UserContext
from ..ingestion.repository_manager import repo_manager
from ...models.repository import RepositorySummary

logger = logging.getLogger(__name__)


def require_repo_access(
    repo_id: str,
    user: UserContext,
    allow_unowned_read: bool = False,
) -> Optional[RepositorySummary]:
    """
    Enforces repository authorization.
    Rejects requests where:
    - User has no access to the repository (403 Forbidden).
    - Repository owner_id is missing/empty (empty owner_id is NOT treated as public unless allow_unowned_read=True).
    """
    clean_repo_id = (repo_id or "").strip()
    if not clean_repo_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository ID must be specified.",
        )

    repo = repo_manager.get_repository(clean_repo_id)
    if repo is not None:
        if not repo.owner_id:
            if allow_unowned_read:
                return repo
            logger.warning(
                f"Security: User '{user.id}' attempted mutating action on unowned repository '{clean_repo_id}'."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You do not have permission to access this repository.",
            )
        if repo.owner_id != user.id:
            logger.warning(
                f"Security: User '{user.id}' attempted unauthorized access to repository '{clean_repo_id}' (owner: '{repo.owner_id}')."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You do not have permission to access this repository.",
            )
        return repo

    return None
