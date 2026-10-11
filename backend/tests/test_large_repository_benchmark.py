"""
Automated regression test verifying scalability on a 5,000+ LOC codebase (Step 33).
Ref: PRD Section 6, Section 11; Step 33 of execution guide.
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.benchmark_large_repo import generate_large_representative_repo
from app.services.filtering.scanner import scan_and_filter_repository
from app.services.parser.file_reader import read_source_file
from app.services.parser.chunker import chunk_file_content
from app.services.indexing.embeddings import MockEmbeddingProvider
from app.services.indexing.storage import PersistentIndexStore
from app.services.retrieval.hybrid import HybridRetrievalManager
from app.services.llm.client import MockLLMProvider
from app.services.llm.qa_service import QAService
from app.models.chat import ChatRequest


def test_large_repository_scalability_and_indexing(tmp_path: Path):
    """Verifies scanning, filtering, chunking, and retrieval on 5,000+ LOC repo."""
    repo_dir = tmp_path / "large_repo"
    info = generate_large_representative_repo(repo_dir)

    assert info["total_lines"] >= 5000, f"Expected at least 5000 LOC, got {info['total_lines']}"

    # 1. Scan and filter
    report = scan_and_filter_repository(repo_dir)
    assert report.total_included == info["included_files_count"]
    assert report.total_skipped >= 4  # .env, node_modules, dist, diagram.png

    # 2. Chunking
    chunks = []
    total_loc = 0
    for rel_path in report.included_files:
        full_path = repo_dir / rel_path
        res = read_source_file(full_path, repo_root=repo_dir)
        assert res.is_success is True
        total_loc += res.line_count
        lang = report.language_breakdown.get(rel_path, "Text")
        file_chunks = chunk_file_content(
            repo_id="test-5k-loc",
            file_path=rel_path,
            content=res.content,
            language=lang,
        )
        chunks.extend(file_chunks)

    assert total_loc >= 5000
    assert len(chunks) >= 80

    # 3. Embedding and Index Store
    embed = MockEmbeddingProvider(dimension=384)
    vectors = embed.embed_texts([c.content for c in chunks])
    store = PersistentIndexStore(repo_id="test-5k-loc", custom_base_dir=tmp_path / "indices")
    store.save(chunks, vectors, "mock", "mock-384", 384)

    # 4. Retrieval & QA
    from unittest.mock import MagicMock
    mock_storage = MagicMock()
    mock_storage.get_store.return_value = store
    retrieval_mgr = HybridRetrievalManager(storage_manager=mock_storage)
    qa = QAService(retrieval_manager=retrieval_mgr, llm_provider=MockLLMProvider())

    resp = qa.answer_question(ChatRequest(
        repo_id="test-5k-loc",
        question="Where is the billing or payment logic implemented?",
    ))

    assert resp.abstained is False
    assert len(resp.citations) >= 1
    paths = [c.file_path.replace('\\', '/') for c in resp.citations]
    assert any("billing" in p or "service" in p or "backend" in p or "docs" in p for p in paths)
