"""
Repository state management and temporary storage isolation.
Ref: PRD Section 9, 10; Step 9 of execution guide.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Optional
import uuid

from ...core.config import get_settings
from ...models.repository import (
    RepositoryStatus,
    SourceType,
    RepositoryStats,
    RepositorySummary,
)

settings = get_settings()


class RepositoryManager:
    """Manages repository records, storage directories, and cleanup."""

    def __init__(self):
        self._repositories: dict[str, RepositorySummary] = {}
        self._load_persisted_repositories()

    def _load_persisted_repositories(self) -> None:
        """Loads repository metadata from disk if available."""
        settings.ensure_storage_dirs()
        for meta_file in settings.data_dir.glob("*/metadata.json"):
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                repo = RepositorySummary(**data)
                self._repositories[repo.repo_id] = repo
            except Exception:
                continue

    def create_repository(
        self,
        name: str,
        source_type: SourceType,
        stats: Optional[RepositoryStats] = None,
    ) -> RepositorySummary:
        """Initializes a new isolated repository entry."""
        repo_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        repo = RepositorySummary(
            repo_id=repo_id,
            name=name,
            source_type=source_type,
            status=RepositoryStatus.PROCESSING,
            created_at=created_at,
            stats=stats or RepositoryStats(),
        )
        self._repositories[repo_id] = repo
        self.save_metadata(repo)
        return repo

    def get_repo_dir(self, repo_id: str) -> Path:
        """Returns the isolated extraction directory for repo_id."""
        return settings.temp_storage_dir / repo_id

    def get_index_dir(self, repo_id: str) -> Path:
        """Returns the isolated persistent index directory for repo_id."""
        return settings.indices_dir / repo_id

    def get_metadata_path(self, repo_id: str) -> Path:
        repo_data_dir = settings.data_dir / repo_id
        repo_data_dir.mkdir(parents=True, exist_ok=True)
        return repo_data_dir / "metadata.json"

    def save_metadata(self, repo: RepositorySummary) -> None:
        """Persists repository metadata to disk."""
        self._repositories[repo.repo_id] = repo
        meta_path = self.get_metadata_path(repo.repo_id)
        meta_path.write_text(repo.model_dump_json(indent=2), encoding="utf-8")

    def update_status(
        self,
        repo_id: str,
        status: RepositoryStatus,
        stats: Optional[RepositoryStats] = None,
    ) -> Optional[RepositorySummary]:
        repo = self._repositories.get(repo_id)
        if not repo:
            return None
        repo.status = status
        if stats:
            repo.stats = stats
        self.save_metadata(repo)
        return repo

    def get_repository(self, repo_id: str) -> Optional[RepositorySummary]:
        return self._repositories.get(repo_id)

    def list_repositories(self) -> list[RepositorySummary]:
        return list(self._repositories.values())

    def cleanup_repository(self, repo_id: str) -> None:
        """Safely cleans up temporary and data directories for a repository."""
        # 1. Temp extraction dir
        temp_dir = self.get_repo_dir(repo_id)
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

        # 2. Data metadata dir
        meta_dir = settings.data_dir / repo_id
        if meta_dir.exists():
            shutil.rmtree(meta_dir, ignore_errors=True)

        # 3. Index dir
        index_dir = self.get_index_dir(repo_id)
        if index_dir.exists():
            shutil.rmtree(index_dir, ignore_errors=True)

        # Remove from in-memory cache
        self._repositories.pop(repo_id, None)


# Global singleton instance
repo_manager = RepositoryManager()
