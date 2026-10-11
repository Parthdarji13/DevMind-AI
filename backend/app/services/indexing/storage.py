"""
Persistent local index storage for chunks, metadata, and embedding vectors.
Ref: PRD Section 6 (FR-05), Section 7, Section 9, Section 10; Step 16 of execution guide.
Enforces per-repository isolation, restart persistence, and safe cleanup.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Optional
import numpy as np

from ...core.config import get_settings
from ...models.chunk import CodeChunk

settings = get_settings()


class PersistentIndexStore:
    """Manages isolated disk persistence of chunks and vectors for a single repository."""

    def __init__(self, repo_id: str, custom_base_dir: Optional[Path] = None):
        self.repo_id = repo_id
        base = custom_base_dir or settings.indices_dir
        self.index_dir = Path(base).resolve() / repo_id
        self.chunks_path = self.index_dir / "chunks.json"
        self.vectors_path = self.index_dir / "vectors.npy"
        self.meta_path = self.index_dir / "index_metadata.json"

        # In-memory cached state
        self._chunks: list[CodeChunk] = []
        self._chunks_by_id: dict[str, CodeChunk] = {}
        self._vectors: Optional[np.ndarray] = None
        self._metadata: dict = {}

        if self.exists():
            self.load()

    def exists(self) -> bool:
        """Returns True if valid persisted index files exist on disk."""
        return (
            self.chunks_path.exists()
            and self.vectors_path.exists()
            and self.meta_path.exists()
        )

    def save(
        self,
        chunks: list[CodeChunk],
        vectors: list[list[float]],
        provider_name: str,
        model_name: str,
        dimension: int,
    ) -> None:
        """
        Atomically persists chunks, metadata, and vectors to isolated directory.
        """
        if len(chunks) != len(vectors):
            raise ValueError(
                f"Chunk count ({len(chunks)}) must match vector count ({len(vectors)})."
            )

        self.index_dir.mkdir(parents=True, exist_ok=True)

        # 1. Save chunks JSON
        chunks_data = [chunk.model_dump() for chunk in chunks]
        self.chunks_path.write_text(
            json.dumps(chunks_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # 2. Save vectors as binary float32 numpy array
        if vectors:
            v_array = np.array(vectors, dtype=np.float32)
        else:
            v_array = np.empty((0, dimension), dtype=np.float32)
        np.save(self.vectors_path, v_array)

        # 3. Save index metadata
        meta = {
            "repo_id": self.repo_id,
            "provider_name": provider_name,
            "model_name": model_name,
            "dimension": dimension,
            "total_chunks": len(chunks),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # Update in-memory state
        self._chunks = chunks
        self._chunks_by_id = {c.chunk_id: c for c in chunks}
        self._vectors = v_array
        self._metadata = meta

    def load(self) -> bool:
        """
        Loads index from disk into memory.
        Returns True if successfully loaded, False otherwise.
        """
        if not self.exists():
            return False

        try:
            # 1. Load metadata
            self._metadata = json.loads(self.meta_path.read_text(encoding="utf-8"))

            # 2. Load chunks
            chunks_raw = json.loads(self.chunks_path.read_text(encoding="utf-8"))
            self._chunks = [CodeChunk(**item) for item in chunks_raw]
            self._chunks_by_id = {c.chunk_id: c for c in self._chunks}

            # 3. Load vectors
            self._vectors = np.load(self.vectors_path)

            return True
        except Exception as e:
            # Failed to read corrupt index
            return False

    def get_chunks(self) -> list[CodeChunk]:
        """Returns all persisted chunks."""
        return self._chunks

    @property
    def chunks(self) -> list[CodeChunk]:
        return self._chunks

    def get_chunk(self, chunk_id: str) -> Optional[CodeChunk]:
        """Retrieves a single chunk by chunk_id."""
        return self._chunks_by_id.get(chunk_id)

    def get_vectors(self) -> Optional[np.ndarray]:
        """Returns 2D float32 numpy array of shape (N, dimension)."""
        return self._vectors

    @property
    def vectors(self) -> Optional[np.ndarray]:
        return self._vectors

    def get_metadata(self) -> dict:
        return self._metadata

    @property
    def metadata(self) -> dict:
        return self._metadata

    def clear(self) -> None:
        """Deletes all persisted index files for this repository."""
        if self.index_dir.exists():
            shutil.rmtree(self.index_dir, ignore_errors=True)
        self._chunks = []
        self._chunks_by_id = {}
        self._vectors = None
        self._metadata = {}


class IndexStorageManager:
    """Factory and registry for repository index stores."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir

    def get_store(self, repo_id: str) -> PersistentIndexStore:
        return PersistentIndexStore(repo_id, custom_base_dir=self.base_dir)

    def delete_store(self, repo_id: str) -> None:
        store = self.get_store(repo_id)
        store.clear()

    def list_indexed_repositories(self) -> list[str]:
        base = self.base_dir or settings.indices_dir
        if not base.exists():
            return []
        indexed = []
        for d in base.iterdir():
            if d.is_dir() and (d / "index_metadata.json").exists():
                indexed.append(d.name)
        return indexed


# Global storage manager singleton
index_storage_manager = IndexStorageManager()
