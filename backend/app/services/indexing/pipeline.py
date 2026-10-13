"""
End-to-end repository indexing pipeline for DevMind AI.
Orchestrates:
1. Reading included source files with SafeFileReader.
2. Chunking code via chunk_file_content (preserving file paths and 1-indexed line numbers).
3. Embedding chunks in batches via get_embedding_provider().
4. Persisting chunks and vectors via PersistentIndexStore.
5. Updating IngestionProgress stages and reconciled metrics in real time.
"""
import logging
import time
from pathlib import Path
from typing import Optional

from ...core.config import get_settings
from ...models.chunk import CodeChunk
from ...models.repository import RepositoryStatus, StageStatus
from ..filtering.scanner import scan_and_filter_repository, detect_language
from ..parser.file_reader import read_source_file
from ..parser.chunker import chunk_file_content
from .embeddings import get_embedding_provider
from ..indexing.storage import PersistentIndexStore
from ..ingestion.progress_tracker import ProgressTracker
from ..ingestion.repository_manager import repo_manager

logger = logging.getLogger(__name__)
settings = get_settings()


def run_repository_indexing(repo_id: str) -> bool:
    """
    Executes stages 3 (Chunking), 4 (Building search index), and 5 (Ready)
    for an ingested repository. Automatically recovers missing repository files
    for Git sources if the server container restarted.
    """
    start_time = time.time()
    repo = repo_manager.get_repository(repo_id)
    if not repo:
        logger.error(f"Cannot index repository '{repo_id}': not found in repository manager.")
        return False

    target_dir = repo_manager.get_repo_dir(repo_id)
    if not target_dir.exists():
        if repo.git_url:
            logger.info(f"Target dir {target_dir} missing on disk; re-cloning from {repo.git_url}...")
            try:
                from ..ingestion.git_cloner import clone_and_filter_public_repo
                clone_and_filter_public_repo(
                    raw_url=repo.git_url,
                    target_dir=target_dir,
                    limits=settings.limits,
                    resolve_dns=True,
                )
            except Exception as e:
                logger.error(f"Failed to auto-restore Git repository '{repo_id}': {e}", exc_info=True)
                if repo.progress:
                    ProgressTracker.fail(repo.progress, 3, f"Failed to restore repository files: {str(e)}")
                    repo_manager.update_progress(repo_id, repo.progress)
                repo_manager.update_status(repo_id, RepositoryStatus.FAILED)
                return False
        else:
            logger.error(f"Cannot index repository '{repo_id}': target dir {target_dir} does not exist.")
            if repo.progress:
                ProgressTracker.fail(repo.progress, 3, "Extracted repository directory not found on disk.")
                repo_manager.update_progress(repo_id, repo.progress)
            repo_manager.update_status(repo_id, RepositoryStatus.FAILED)
            return False

    progress = repo.progress
    if not progress:
        logger.warning(f"Repository '{repo_id}' has no progress tracker attached.")
        return False

    try:
        # 1. Gather included files from filtering scan
        filter_report = scan_and_filter_repository(target_dir, limits=settings.limits)
        included_files = filter_report.included_files
        total_files = len(included_files)

        if total_files == 0:
            ProgressTracker.fail(progress, 3, "No supported source code files available to index.")
            repo_manager.update_progress(repo_id, progress)
            repo_manager.update_status(repo_id, RepositoryStatus.FAILED)
            return False

        # --- STAGE 3: Chunking code ---
        ProgressTracker.advance_to_stage(
            progress,
            step_number=3,
            status=StageStatus.IN_PROGRESS,
            detail=f"Chunking 0 of {total_files} source files...",
            current_count=0,
            total_count=total_files,
        )
        repo_manager.update_progress(repo_id, progress)

        all_chunks: list[CodeChunk] = []
        total_lines_read = 0
        failed_files_count = 0

        for idx, rel_path in enumerate(included_files, start=1):
            full_path = target_dir / rel_path
            read_result = read_source_file(
                full_path,
                repo_root=target_dir,
                max_file_bytes=settings.limits.max_file_bytes,
            )

            if not read_result.is_success:
                failed_files_count += 1
                continue

            total_lines_read += read_result.line_count
            lang = detect_language(rel_path)
            file_chunks = chunk_file_content(
                repo_id=repo_id,
                file_path=rel_path,
                content=read_result.content,
                language=lang,
            )
            all_chunks.extend(file_chunks)

            # Update progress frequently so user sees live file progress
            update_interval = 2 if total_files > 20 else 1
            if idx % update_interval == 0 or idx == total_files:
                ProgressTracker.advance_to_stage(
                    progress,
                    step_number=3,
                    status=StageStatus.IN_PROGRESS,
                    detail=f"Chunking {idx} of {total_files} files ({len(all_chunks)} chunks generated)...",
                    current_count=idx,
                    total_count=total_files,
                )
                repo_manager.update_progress(repo_id, progress)

        ProgressTracker.complete_stage(
            progress,
            step_number=3,
            detail=f"Generated {len(all_chunks)} syntax-bounded chunks across {total_files - failed_files_count} files",
        )
        repo_manager.update_progress(repo_id, progress)

        # --- STAGE 4: Building search index ---
        total_chunks = len(all_chunks)
        ProgressTracker.advance_to_stage(
            progress,
            step_number=4,
            status=StageStatus.IN_PROGRESS,
            detail=f"Computing embeddings for {total_chunks} chunks...",
            current_count=0,
            total_count=total_chunks,
        )
        repo_manager.update_progress(repo_id, progress)

        embedding_provider = get_embedding_provider()
        chunk_texts = [c.content for c in all_chunks]

        # Compute embeddings incrementally in batches and report live progress
        batch_size = 20
        vectors: list[list[float]] = []

        for i in range(0, total_chunks, batch_size):
            batch_slice = chunk_texts[i : i + batch_size]
            batch_vectors = embedding_provider.embed_texts(batch_slice, batch_size=len(batch_slice))
            vectors.extend(batch_vectors)

            done_chunks = len(vectors)
            ProgressTracker.advance_to_stage(
                progress,
                step_number=4,
                status=StageStatus.IN_PROGRESS,
                detail=f"Computing embeddings for {done_chunks} of {total_chunks} chunks...",
                current_count=done_chunks,
                total_count=total_chunks,
            )
            repo_manager.update_progress(repo_id, progress)
            # Gentle pacing so frontend polling captures intermediate batches smoothly
            time.sleep(0.04)

        # Save to isolated persistent index store
        store = PersistentIndexStore(repo_id=repo_id)
        store.save(
            chunks=all_chunks,
            vectors=vectors,
            provider_name=settings.embedding_provider,
            model_name=embedding_provider.model_name,
            dimension=embedding_provider.dimension,
        )

        ProgressTracker.complete_stage(
            progress,
            step_number=4,
            detail=f"Built persistent BM25 & vector index with {total_chunks} chunks",
        )
        repo_manager.update_progress(repo_id, progress)

        # --- STAGE 5: Ready for questions ---
        duration = round(time.time() - start_time, 2)
        ProgressTracker.set_metrics(
            progress,
            discovered=filter_report.total_discovered,
            included=filter_report.total_included,
            skipped=filter_report.total_skipped,
            failed=failed_files_count,
            indexed=total_files - failed_files_count,
            total_lines=total_lines_read,
            duration_seconds=duration,
            skipped_breakdown=filter_report.skipped_breakdown,
            languages=filter_report.language_breakdown,
        )

        ProgressTracker.complete_stage(
            progress,
            step_number=5,
            detail=f"Repository ready for evidence-grounded Q&A ({len(all_chunks)} chunks, {duration}s)",
        )
        repo_manager.update_progress(repo_id, progress)

        # Update repository stats and state
        repo_manager.update_status(
            repo_id=repo_id,
            status=RepositoryStatus.READY,
        )
        if repo.stats:
            repo.stats.indexed_files = total_files - failed_files_count
            repo.stats.total_lines = total_lines_read
            repo.stats.duration_seconds = duration

        logger.info(f"Repository '{repo_id}' successfully indexed in {duration}s.")
        return True

    except Exception as e:
        logger.error(f"Error indexing repository '{repo_id}': {e}", exc_info=True)
        if progress:
            current_step = progress.current_step if progress.current_step else 3
            ProgressTracker.fail(progress, current_step, f"Indexing failed: {str(e)}")
            repo_manager.update_progress(repo_id, progress)
        repo_manager.update_status(repo_id, RepositoryStatus.FAILED)
        return False
