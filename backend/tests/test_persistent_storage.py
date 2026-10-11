"""
Unit tests for Persistent Index Storage and Repository Isolation (Step 16).
Verifies:
- Chunks, metadata, and vectors persist to disk and survive process restart.
- Strict isolation between repositories (no chunk or vector leakage).
- Clean index cleanup and re-indexing support.
"""
import sys
from pathlib import Path
import numpy as np
import pytest

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.chunk import CodeChunk
from app.services.indexing.storage import (
    PersistentIndexStore,
    IndexStorageManager,
)


def create_sample_chunk(repo_id: str, file_path: str, idx: int) -> CodeChunk:
    return CodeChunk(
        chunk_id=f"chk_{repo_id}_{idx}",
        repo_id=repo_id,
        file_path=file_path,
        language="Python",
        start_line=idx * 10 + 1,
        end_line=idx * 10 + 10,
        content=f"# Code for {file_path} chunk {idx}",
        chunk_index=idx,
        symbol_name=f"func_{idx}",
        line_count=10,
        char_count=30,
    )


def test_persistence_survives_process_restart(tmp_path):
    repo_id = "repo-restart-test"
    store = PersistentIndexStore(repo_id=repo_id, custom_base_dir=tmp_path)

    assert not store.exists()

    # Create 3 chunks and dummy vectors
    chunks = [create_sample_chunk(repo_id, "main.py", i) for i in range(3)]
    vectors = [[float(i + j) for j in range(4)] for i in range(3)]

    store.save(
        chunks=chunks,
        vectors=vectors,
        provider_name="local",
        model_name="local-semantic-384",
        dimension=4,
    )

    assert store.exists()
    assert len(store.get_chunks()) == 3

    # Simulate restart by instantiating a fresh store pointing to same directory
    restarted_store = PersistentIndexStore(repo_id=repo_id, custom_base_dir=tmp_path)
    assert restarted_store.exists()

    loaded_chunks = restarted_store.get_chunks()
    assert len(loaded_chunks) == 3
    assert loaded_chunks[0].chunk_id == "chk_repo-restart-test_0"
    assert loaded_chunks[1].content == chunks[1].content
    assert loaded_chunks[2].start_line == chunks[2].start_line

    loaded_vectors = restarted_store.get_vectors()
    assert loaded_vectors.shape == (3, 4)
    assert np.allclose(loaded_vectors[0], [0.0, 1.0, 2.0, 3.0])

    meta = restarted_store.get_metadata()
    assert meta["repo_id"] == repo_id
    assert meta["total_chunks"] == 3


def test_repository_isolation(tmp_path):
    mgr = IndexStorageManager(base_dir=tmp_path)

    # Store Repo A
    store_a = mgr.get_store("repo-alpha")
    chunks_a = [create_sample_chunk("repo-alpha", "alpha.py", i) for i in range(2)]
    vectors_a = [[1.0, 0.0] for _ in range(2)]
    store_a.save(chunks_a, vectors_a, "mock", "mock-2", 2)

    # Store Repo B
    store_b = mgr.get_store("repo-beta")
    chunks_b = [create_sample_chunk("repo-beta", "beta.py", i) for i in range(4)]
    vectors_b = [[0.0, 1.0] for _ in range(4)]
    store_b.save(chunks_b, vectors_b, "mock", "mock-2", 2)

    # Verify isolation
    assert len(store_a.get_chunks()) == 2
    assert len(store_b.get_chunks()) == 4

    assert store_a.get_chunk("chk_repo-alpha_0") is not None
    assert store_a.get_chunk("chk_repo-beta_0") is None  # No cross-repo chunk leakage

    assert store_b.get_chunk("chk_repo-beta_0") is not None
    assert store_b.get_chunk("chk_repo-alpha_0") is None

    # Verify vector isolation
    assert store_a.get_vectors().shape == (2, 2)
    assert store_b.get_vectors().shape == (4, 2)


def test_clear_and_reindex(tmp_path):
    mgr = IndexStorageManager(base_dir=tmp_path)
    store = mgr.get_store("repo-cleanup")

    chunks = [create_sample_chunk("repo-cleanup", "mod.py", 0)]
    vectors = [[0.5, 0.5]]
    store.save(chunks, vectors, "mock", "mock-2", 2)
    assert store.exists()

    # Clear
    store.clear()
    assert not store.exists()
    assert len(store.get_chunks()) == 0
    assert store.get_vectors() is None

    # Re-index
    new_chunks = [create_sample_chunk("repo-cleanup", "mod2.py", 0)]
    new_vectors = [[0.8, 0.8]]
    store.save(new_chunks, new_vectors, "mock", "mock-2", 2)
    assert store.exists()
    assert len(store.get_chunks()) == 1
    assert store.get_chunks()[0].file_path == "mod2.py"
