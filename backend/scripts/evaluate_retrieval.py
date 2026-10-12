"""
DevMind AI — Retrieval Evaluation Benchmark Script (Step 33 / PRD Section 18).
Evaluates retrieval accuracy (Recall@1, Recall@3, Recall@5, MRR, Latency) across:
1. BM25 Lexical Search Alone
2. Dense Vector Semantic Search Alone (FastEmbed / all-MiniLM-L6-v2)
3. Hybrid Search (BM25 + Dense Vectors via Reciprocal Rank Fusion)

Measures PRD success metrics against a 15-query ground-truth benchmark suite.
Outputs comparative table to console and saves report to JSON and Markdown.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
import sys
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.models.chunk import CodeChunk
from backend.app.services.indexing.embeddings import FastEmbedEmbeddingProvider, get_embedding_provider
from backend.app.services.parser.chunker import chunk_file_content
from backend.app.services.parser.file_reader import read_source_file
from backend.app.services.indexing.storage import PersistentIndexStore
from backend.app.services.retrieval.hybrid import HybridRetriever


BENCHMARK_MODULES = {
    "services/auth.py": '''"""User authentication, JWT token generation, and credential verification."""
import hmac
import hashlib
import time

def sign_jwt_token(user_id: str, secret_key: str, expires_in: int = 3600) -> str:
    """Signs an HMAC-SHA256 JWT access token with user claims and expiration timestamp."""
    header = "eyJhbGciOiJIUzI1NiJ9"
    payload = f'{{"sub":"{user_id}","exp":{int(time.time()) + expires_in}}}'
    signing_input = f"{header}.{payload}".encode("utf-8")
    sig = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).hexdigest()
    return f"{header}.{payload}.{sig}"

def verify_token(token: str, secret_key: str) -> bool:
    """Verifies JWT token signature and expiration validity."""
    parts = token.split(".")
    if len(parts) != 3:
        return False
    header, payload, sig = parts
    signing_input = f"{header}.{payload}".encode("utf-8")
    expected = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)
''',

    "services/database.py": '''"""MongoDB Atlas connection pooling and multi-tenant chat turn storage."""
from typing import Dict, Any, List

class MongoAtlasStore:
    """Handles persistence of users, repositories, and conversation history in MongoDB."""
    def __init__(self, uri: str, db_name: str = "devmind_ai"):
        self.uri = uri
        self.db_name = db_name
        self.client = None

    def connect(self):
        """Initializes connection to MongoDB Atlas cluster."""
        print(f"Connecting to MongoDB cluster: {self.db_name}")

    def save_chat_turn(self, repo_id: str, session_id: str, user_msg: str, assistant_msg: str, citations: list):
        """Persists a verified question-answer turn with citations into MongoDB Atlas collection."""
        record = {
            "repo_id": repo_id,
            "session_id": session_id,
            "user_message": user_msg,
            "assistant_message": assistant_msg,
            "citations": citations,
        }
        return record
''',

    "services/git_cloner.py": '''"""Git repository cloner with shallow cloning and timeout enforcement."""
import subprocess
from pathlib import Path

class GitTimeoutError(Exception):
    """Raised when git clone exceeds configured timeout seconds."""
    pass

def clone_public_repo(repo_url: str, target_dir: Path, timeout_seconds: int = 30) -> Path:
    """Executes git clone --depth 1 with strict subprocess timeout."""
    cmd = ["git", "clone", "--depth", "1", repo_url, str(target_dir)]
    try:
        subprocess.run(cmd, check=True, timeout=timeout_seconds, capture_output=True)
    except subprocess.TimeoutExpired as e:
        raise GitTimeoutError(f"Cloning {repo_url} timed out after {timeout_seconds}s") from e
    return target_dir
''',

    "services/vector_search.py": '''"""Dense vector search using normalized cosine dot-product indexing."""
import numpy as np

class DenseVectorIndex:
    """Computes cosine similarity between query embeddings and indexed code chunk vectors."""
    def __init__(self, vectors: np.ndarray, chunk_ids: list):
        self.vectors = vectors  # L2-normalized vectors
        self.chunk_ids = chunk_ids

    def search_similar(self, query_vector: list, top_k: int = 10) -> list:
        """Finds top-k nearest code chunks using matrix dot product cosine similarity."""
        q_vec = np.array(query_vector, dtype=np.float32)
        norm = np.linalg.norm(q_vec)
        if norm > 0:
            q_vec = q_vec / norm
        scores = np.dot(self.vectors, q_vec)
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(self.chunk_ids[i], float(scores[i])) for i in top_indices]
''',

    "services/hybrid_search.py": '''"""Reciprocal Rank Fusion (RRF) combining lexical and vector search scores."""
def reciprocal_rank_fusion(lexical_ranks: list, vector_ranks: list, rrf_k: int = 60) -> list:
    """Combines ranking lists using formula: score = sum(weight / (rrf_k + rank))."""
    scores = {}
    for rank, item_id in enumerate(lexical_ranks):
        scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (rrf_k + rank + 1)
    for rank, item_id in enumerate(vector_ranks):
        scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (rrf_k + rank + 1)
    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_items
''',

    "services/citation_validator.py": '''"""Validates LLM-generated citations against indexed chunk line numbers."""
import re

def validate_citations_in_text(answer_text: str, source_chunks: list) -> list:
    """Extracts inline citation references like [file.py:10-25] and verifies validity."""
    pattern = r"\\[([^\\]:]+):(\\d+)-(\\d+)\\]"
    found = re.findall(pattern, answer_text)
    validated = []
    for file_path, start_str, end_str in found:
        start_line, end_line = int(start_str), int(end_str)
        for chunk in source_chunks:
            if chunk.file_path == file_path and chunk.start_line <= start_line and chunk.end_line >= end_line:
                validated.append({"file_path": file_path, "start_line": start_line, "end_line": end_line})
                break
    return validated
''',

    "services/file_scanner.py": '''"""File filtering scanner excluding build artifacts, node_modules, and git locks."""
import os
from pathlib import Path

EXCLUDED_DIRS = {".git", "node_modules", "__pycache__", "dist", "build", ".venv"}
EXCLUDED_EXTENSIONS = {".lock", ".pyc", ".png", ".jpg", ".exe", ".bin"}

def should_index_file(file_path: Path) -> bool:
    """Returns True if file is supported text source code and not excluded."""
    for part in file_path.parts:
        if part in EXCLUDED_DIRS:
            return False
    if file_path.suffix.lower() in EXCLUDED_EXTENSIONS:
        return False
    return True
''',

    "services/ast_chunker.py": '''"""AST-aware code chunker respecting function and class boundary semantics."""
import ast

def chunk_python_source(code_text: str, file_path: str, max_chunk_lines: int = 60) -> list:
    """Parses Python Abstract Syntax Tree and chunks functions, classes, and top-level statements."""
    try:
        tree = ast.parse(code_text)
    except SyntaxError:
        return [{"file_path": file_path, "start_line": 1, "end_line": len(code_text.splitlines())}]
    chunks = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            chunks.append({
                "file_path": file_path,
                "name": node.name,
                "start_line": node.lineno,
                "end_line": node.end_lineno or node.lineno,
            })
    return chunks
''',

    "services/security_validator.py": '''"""Zip-Slip path traversal security mitigation and archive sanity check."""
import os
from pathlib import Path

def is_safe_zip_path(dest_directory: Path, target_path: str) -> bool:
    """Ensures extracted file cannot escape dest_directory via Zip-Slip traversal like ../../etc/passwd."""
    resolved_dest = dest_directory.resolve()
    resolved_target = (dest_directory / target_path).resolve()
    try:
        resolved_target.relative_to(resolved_dest)
        return True
    except ValueError:
        return False
''',

    "services/access_control.py": '''"""Multi-tenant authorization enforcing repository ownership checks."""
class AccessControlManager:
    """Prevents cross-tenant data leakage by checking repository owner_id against user_id."""
    def enforce_repo_access(self, repo_owner_id: str, current_user_id: str) -> bool:
        """Raises 403 Forbidden if repository is not owned by the authenticated user."""
        if not repo_owner_id or repo_owner_id != current_user_id:
            raise PermissionError("Access denied: You do not have permission to access this repository.")
        return True
''',

    "api/routes_stream.py": '''"""Server-Sent Events (SSE) streaming answers endpoint."""
from fastapi.responses import StreamingResponse

def stream_chat_answer(token_generator):
    """Wraps an asynchronous token generator into a real-time text/event-stream HTTP response."""
    return StreamingResponse(
        token_generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
''',

    "services/gemini_stream.py": '''"""Google Gemini LLM SSE stream generator with progressive token yields."""
def generate_gemini_stream(prompt: str, api_key: str):
    """Calls Gemini streamGenerateContent?alt=sse and yields incremental token events."""
    tokens = ["This ", "function ", "implements ", "token ", "streaming."]
    for t in tokens:
        yield f"event: token\\ndata: {{\\"token\\": \\"{t}\\"}}\\n\\n"
    yield f"event: done\\ndata: {{\\"status\\": \\"completed\\"}}\\n\\n"
''',

    "services/progress_tracker.py": '''"""Five-stage ingestion progress tracker with live counters."""
class IngestionProgressTracker:
    """Monitors 5 ingestion stages: discover, read, chunk, embed, and index."""
    STAGES = ["discover", "read", "chunk", "embed", "index"]

    def __init__(self, repo_id: str):
        self.repo_id = repo_id
        self.stage = "discover"
        self.processed_files = 0
        self.total_files = 0

    def advance_stage(self, new_stage: str):
        """Advances repository ingestion status to next pipeline milestone."""
        self.stage = new_stage
''',

    "config/limits.py": '''"""Ingestion boundary limits and resource allocation safeguards."""
MAX_ZIP_MB = 100
MAX_FILES = 3000
MAX_FILE_KB = 1000
RETENTION_DAYS = 7
GIT_CLONE_TIMEOUT_SECONDS = 30
''',

    "config/settings.py": '''"""Application configuration loader for MongoDB URI, JWT secret, and API keys."""
import os

class AppSettings:
    """Loads environment variables for FastAPI, MongoDB Atlas, and LLM providers."""
    def __init__(self):
        self.mongodb_uri = os.getenv("MONGODB_URI", "mongodb+srv://user:pass@cluster.mongodb.net")
        self.mongodb_db_name = os.getenv("MONGODB_DB_NAME", "devmind_ai")
        self.jwt_secret = os.getenv("JWT_SECRET", "devmind_ai_secure_signing_secret_key")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
'''
}


GROUND_TRUTH_EVALUATION_SUITE = [
    {
        "id": "q01",
        "query": "How are JWT bearer tokens signed and verified?",
        "expected_file": "services/auth.py",
        "description": "Security & JWT Token Signing",
    },
    {
        "id": "q02",
        "query": "Where is chat history persisted to MongoDB Atlas collection?",
        "expected_file": "services/database.py",
        "description": "Database Persistence & Mongo Atlas",
    },
    {
        "id": "q03",
        "query": "How does the cloner handle git clone timeout?",
        "expected_file": "services/git_cloner.py",
        "description": "Git Ingestion & Process Timeouts",
    },
    {
        "id": "q04",
        "query": "Where is vector cosine dot product similarity computed?",
        "expected_file": "services/vector_search.py",
        "description": "Dense Vector Search & Cosine Scoring",
    },
    {
        "id": "q05",
        "query": "How does Reciprocal Rank Fusion combine ranking scores?",
        "expected_file": "services/hybrid_search.py",
        "description": "Hybrid Rank Fusion (RRF)",
    },
    {
        "id": "q06",
        "query": "Where are line numbers and file citations verified?",
        "expected_file": "services/citation_validator.py",
        "description": "Citation Validation & Verification",
    },
    {
        "id": "q07",
        "query": "How are git lock files and node_modules excluded?",
        "expected_file": "services/file_scanner.py",
        "description": "Filtering Scanner & Exclusions",
    },
    {
        "id": "q08",
        "query": "Where are functions and classes parsed using AST chunking?",
        "expected_file": "services/ast_chunker.py",
        "description": "Code Splitting & AST Boundary Chunking",
    },
    {
        "id": "q09",
        "query": "How is Zip-Slip path traversal vulnerability mitigated?",
        "expected_file": "services/security_validator.py",
        "description": "Security Sanitization & Archive Safety",
    },
    {
        "id": "q10",
        "query": "Where is tenant repository ownership and authorization checked?",
        "expected_file": "services/access_control.py",
        "description": "Multi-tenant Access Control",
    },
    {
        "id": "q11",
        "query": "Where is the Server-Sent Events SSE streaming endpoint handled?",
        "expected_file": "api/routes_stream.py",
        "description": "Real-time Streaming Answer Routes",
    },
    {
        "id": "q12",
        "query": "How does Gemini token streaming yield chunks?",
        "expected_file": "services/gemini_stream.py",
        "description": "LLM Token Stream Generation",
    },
    {
        "id": "q13",
        "query": "Where are 5-stage ingestion progress counters tracked?",
        "expected_file": "services/progress_tracker.py",
        "description": "Ingestion Progress Pipeline Tracking",
    },
    {
        "id": "q14",
        "query": "What is the maximum allowed zip file upload size?",
        "expected_file": "config/limits.py",
        "description": "Ingestion Limits & Safeguards",
    },
    {
        "id": "q15",
        "query": "Where are environment variables and MongoDB URI loaded?",
        "expected_file": "config/settings.py",
        "description": "Configuration & Environment Setup",
    },
]


def prepare_benchmark_repository(target_dir: Path) -> Path:
    """Populates target directory with benchmark code modules."""
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    for rel_path, code in BENCHMARK_MODULES.items():
        file_path = target_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(code, encoding="utf-8")

    return target_dir


def evaluate_retrieval(
    repo_dir: Optional[Path] = None,
    indices_dir: Optional[Path] = None,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Executes the 15-question retrieval benchmark and computes comparative metrics
    for BM25 alone, Dense Vectors alone (FastEmbed), and Hybrid RRF.
    """
    base_dir = repo_dir or Path("data/retrieval_benchmark_repo").resolve()
    store_dir = indices_dir or Path("data/retrieval_benchmark_indices").resolve()
    repo_id = "eval-retrieval-suite-15"

    if verbose:
        print("=" * 80)
        print(" DevMind AI - Retrieval Evaluation Benchmark (15 Questions, Recall@5)")
        print("=" * 80)
        print(f"1. Setting up benchmark codebase at: {base_dir}")

    prepare_benchmark_repository(base_dir)

    # Index using real FastEmbed / SentenceTransformers embedding provider
    if verbose:
        print("2. Indexing repository chunks with real dense embeddings...")

    t0_idx = time.perf_counter()
    all_chunks = []
    for rel_path in BENCHMARK_MODULES.keys():
        full_path = base_dir / rel_path
        read_res = read_source_file(full_path, repo_root=base_dir)
        if read_res.is_success and read_res.content:
            chunks = chunk_file_content(
                repo_id=repo_id,
                file_path=rel_path,
                content=read_res.content,
                language="Python",
            )
            all_chunks.extend(chunks)

    embedding_provider = get_embedding_provider()
    texts = [c.content for c in all_chunks]
    vectors = embedding_provider.embed_texts(texts)

    store = PersistentIndexStore(repo_id, custom_base_dir=store_dir)
    store.save(
        chunks=all_chunks,
        vectors=vectors,
        provider_name=embedding_provider.model_name,
        model_name=embedding_provider.model_name,
        dimension=embedding_provider.dimension,
    )
    t_idx_elapsed = time.perf_counter() - t0_idx

    chunks = store.get_chunks()
    if verbose:
        print(f"   [OK] Chunks created: {len(chunks)} | Embedding model: {embedding_provider.model_name}")
        print(f"   [OK] Indexing duration: {t_idx_elapsed:.2f}s")
        print("\n3. Running 15 Ground-Truth Queries across BM25, Vector, and Hybrid RRF...\n")

    retriever = HybridRetriever.from_store(store, embedding_provider=embedding_provider)

    # Metric accumulators
    methods = ["bm25", "vector", "hybrid"]
    metrics: Dict[str, Dict[str, Any]] = {
        m: {
            "r1_hits": 0,
            "r3_hits": 0,
            "r5_hits": 0,
            "reciprocal_ranks": [],
            "latencies_ms": [],
        }
        for m in methods
    }

    per_query_results = []

    for item in GROUND_TRUTH_EVALUATION_SUITE:
        qid = item["id"]
        query = item["query"]
        expected_file = item["expected_file"]
        desc = item["description"]

        query_record = {
            "id": qid,
            "query": query,
            "expected_file": expected_file,
            "description": desc,
            "ranks": {},
        }

        # 1. BM25 alone
        t0 = time.perf_counter()
        bm25_res = retriever.bm25_index.search(query=query, top_k=10)
        t_bm25 = (time.perf_counter() - t0) * 1000.0

        # 2. Vector search alone
        t0 = time.perf_counter()
        vector_res = retriever.vector_index.search(query=query, top_k=10) if retriever.vector_index else []
        t_vec = (time.perf_counter() - t0) * 1000.0

        # 3. Hybrid RRF
        t0 = time.perf_counter()
        hybrid_res = retriever.retrieve(query=query, top_k=10)
        t_hyb = (time.perf_counter() - t0) * 1000.0

        run_results = {
            "bm25": (bm25_res, t_bm25),
            "vector": (vector_res, t_vec),
            "hybrid": (hybrid_res, t_hyb),
        }

        for m_name, (res_list, lat) in run_results.items():
            metrics[m_name]["latencies_ms"].append(lat)

            # Find rank of expected file
            hit_rank = None
            for r_idx, hit in enumerate(res_list):
                if hit.chunk.file_path == expected_file or hit.chunk.file_path.endswith(expected_file):
                    hit_rank = r_idx + 1  # 1-indexed
                    break

            query_record["ranks"][m_name] = hit_rank

            if hit_rank is not None:
                if hit_rank <= 1:
                    metrics[m_name]["r1_hits"] += 1
                if hit_rank <= 3:
                    metrics[m_name]["r3_hits"] += 1
                if hit_rank <= 5:
                    metrics[m_name]["r5_hits"] += 1
                metrics[m_name]["reciprocal_ranks"].append(1.0 / hit_rank)
            else:
                metrics[m_name]["reciprocal_ranks"].append(0.0)

        per_query_results.append(query_record)

    total_queries = len(GROUND_TRUTH_EVALUATION_SUITE)
    summary: Dict[str, Dict[str, float]] = {}

    for m_name in methods:
        m_data = metrics[m_name]
        r1 = (m_data["r1_hits"] / total_queries) * 100.0
        r3 = (m_data["r3_hits"] / total_queries) * 100.0
        r5 = (m_data["r5_hits"] / total_queries) * 100.0
        mrr = sum(m_data["reciprocal_ranks"]) / total_queries
        avg_lat = sum(m_data["latencies_ms"]) / total_queries

        summary[m_name] = {
            "recall_at_1": round(r1, 1),
            "recall_at_3": round(r3, 1),
            "recall_at_5": round(r5, 1),
            "mrr": round(mrr, 4),
            "avg_latency_ms": round(avg_lat, 2),
        }

    # Print comparative evaluation table
    if verbose:
        print(f"{'QID':<4} | {'Expected Module':<30} | {'BM25 Rank':<10} | {'Vector Rank':<12} | {'Hybrid Rank':<12}")
        print("-" * 76)
        for q in per_query_results:
            bm25_r = f"#{q['ranks']['bm25']}" if q["ranks"]["bm25"] else "MISS"
            vec_r = f"#{q['ranks']['vector']}" if q["ranks"]["vector"] else "MISS"
            hyb_r = f"#{q['ranks']['hybrid']}" if q["ranks"]["hybrid"] else "MISS"
            print(f"{q['id']:<4} | {q['expected_file']:<30} | {bm25_r:<10} | {vec_r:<12} | {hyb_r:<12}")

        print("\n" + "=" * 80)
        print(" RETRIEVAL EVALUATION RESULTS SUMMARY (PRD SUCCESS METRICS)")
        print("=" * 80)
        print(f"{'Retrieval Method':<22} | {'Recall@1':<10} | {'Recall@3':<10} | {'Recall@5':<10} | {'MRR':<8} | {'Latency':<10}")
        print("-" * 80)
        print(f"{'BM25 Lexical Alone':<22} | {summary['bm25']['recall_at_1']}%{'':<4} | {summary['bm25']['recall_at_3']}%{'':<4} | {summary['bm25']['recall_at_5']}%{'':<4} | {summary['bm25']['mrr']:<8.4f} | {summary['bm25']['avg_latency_ms']} ms")
        print(f"{'Dense Vector Alone':<22} | {summary['vector']['recall_at_1']}%{'':<4} | {summary['vector']['recall_at_3']}%{'':<4} | {summary['vector']['recall_at_5']}%{'':<4} | {summary['vector']['mrr']:<8.4f} | {summary['vector']['avg_latency_ms']} ms")
        print(f"{'Hybrid RRF (Fusion)':<22} | {summary['hybrid']['recall_at_1']}%{'':<4} | {summary['hybrid']['recall_at_3']}%{'':<4} | {summary['hybrid']['recall_at_5']}%{'':<4} | {summary['hybrid']['mrr']:<8.4f} | {summary['hybrid']['avg_latency_ms']} ms")
        print("=" * 80)
        print(f"Target PRD Metric (Recall@5 >= 80%): {'PASSED [OK]' if summary['hybrid']['recall_at_5'] >= 80.0 else 'FAILED [X]'}")
        print(f"Evaluated Model: {embedding_provider.model_name} ({embedding_provider.dimension} dimensions)")

    report_payload = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_queries": total_queries,
        "embedding_provider": embedding_provider.model_name,
        "embedding_dimension": embedding_provider.dimension,
        "summary": summary,
        "per_query_results": per_query_results,
    }

    # Save reports
    data_dir = Path("data").resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    json_report_path = data_dir / "retrieval_evaluation_report.json"
    with open(json_report_path, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)

    md_report_path = data_dir / "retrieval_evaluation_report.md"
    md_content = f"""# DevMind AI — Retrieval Evaluation Report

**Generated:** {report_payload['timestamp']}  
**Benchmark Suite:** 15 Diverse Ground-Truth Codebase Queries  
**Embedding Provider:** `{embedding_provider.model_name}` ({embedding_provider.dimension} dimensions)  

## Comparative Retrieval Performance

| Retrieval Method | Recall@1 | Recall@3 | Recall@5 (PRD Target) | MRR | Latency |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **BM25 Lexical** | {summary['bm25']['recall_at_1']}% | {summary['bm25']['recall_at_3']}% | {summary['bm25']['recall_at_5']}% | {summary['bm25']['mrr']:.4f} | {summary['bm25']['avg_latency_ms']} ms |
| **Dense Vector** | {summary['vector']['recall_at_1']}% | {summary['vector']['recall_at_3']}% | {summary['vector']['recall_at_5']}% | {summary['vector']['mrr']:.4f} | {summary['vector']['avg_latency_ms']} ms |
| **Hybrid RRF** | **{summary['hybrid']['recall_at_1']}%** | **{summary['hybrid']['recall_at_3']}%** | **{summary['hybrid']['recall_at_5']}%** | **{summary['hybrid']['mrr']:.4f}** | {summary['hybrid']['avg_latency_ms']} ms |

> **PRD Success Criterion:** Recall@5 $\\ge$ 80% — **{'PASSED ✓' if summary['hybrid']['recall_at_5'] >= 80.0 else 'FAILED ✗'}**
"""
    with open(md_report_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return report_payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate DevMind AI retrieval quality and Recall@5 metric.")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose stdout table")
    args = parser.parse_args()
    evaluate_retrieval(verbose=not args.quiet)
