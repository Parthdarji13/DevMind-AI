"""
End-to-End Test Suite for DevMind AI (Step 32).
Ref: PRD Section 6 (FR-01 to FR-10), Section 7; Step 32 of execution guide.
Verifies all 5 mandatory end-to-end flows:
1. Flow 1: ZIP upload -> indexing -> chat question -> grounded citation.
2. Flow 2: Git URL ingestion -> indexing -> chat question -> grounded citation.
3. Flow 3: Three sequential questions (multi-turn conversation) without state loss.
4. Flow 4: Malformed and adversarial input handling (empty question, oversized input, corrupt zip, private git URL).
5. Flow 5: LLM provider failure handling (rate limits, timeouts, missing keys) without secrets or stack trace leakage.
"""
import io
import subprocess
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app
from app.models.chunk import CodeChunk
from app.services.indexing.embeddings import MockEmbeddingProvider
from app.services.indexing.storage import (
    IndexStorageManager,
    index_storage_manager,
    PersistentIndexStore,
)
from app.services.ingestion.repository_manager import repo_manager
from app.services.ingestion.git_validator import GitValidationResult
from app.services.llm.client import (
    MockLLMProvider,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMConfigurationError,
)
from app.services.llm.qa_service import QAService
from app.services.retrieval.hybrid import HybridRetrievalManager
from app.api.routes_chat import get_qa_service

client = TestClient(app)


def _create_sample_project_zip() -> io.BytesIO:
    """Create a multi-file project zip containing Python and TypeScript code."""
    entries = {
        "src/orders.py": (
            "def calculate_total(items, tax_rate=0.08):\n"
            "    subtotal = sum(item['price'] * item['qty'] for item in items)\n"
            "    tax = subtotal * tax_rate\n"
            "    return subtotal + tax\n"
            "\n"
            "def apply_discount(total, discount_code):\n"
            "    if discount_code == 'SAVE10':\n"
            "        return total * 0.90\n"
            "    return total\n"
        ),
        "src/auth.ts": (
            "export interface UserSession {\n"
            "  userId: string;\n"
            "  roles: string[];\n"
            "}\n"
            "\n"
            "export function validateSession(session: UserSession): boolean {\n"
            "  return Boolean(session && session.userId);\n"
            "}\n"
        ),
        "README.md": "# E2E Test Project\nSample repository for end-to-end testing.",
        ".env": "SECRET_KEY=leak_me_if_you_dare",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in entries.items():
            zf.writestr(path, content)
    buf.seek(0)
    return buf


# ==============================================================================
# FLOW 1: ZIP Upload -> Index -> Question -> Citation
# ==============================================================================
def test_flow_1_zip_upload_to_citation(tmp_path: Path):
    """E2E Flow 1: Upload ZIP, complete indexing, ask question, verify grounded citations."""
    zip_buf = _create_sample_project_zip()

    # 1. Upload ZIP
    upload_resp = client.post(
        "/api/ingest/zip",
        files={"file": ("ecommerce.zip", zip_buf, "application/zip")},
    )
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    repo_id = upload_data["repo_id"]
    assert upload_data["status"] == "ready"
    assert upload_data["stats"]["discovered_files"] == 4
    assert upload_data["stats"]["included_files"] == 3  # .env was filtered out!
    assert upload_data["stats"]["skipped_files"] == 1

    # 2. Verify progress endpoint
    prog_resp = client.get(f"/api/ingest/progress/{repo_id}")
    assert prog_resp.status_code == 200
    prog_data = prog_resp.json()
    assert prog_data["overall_status"] == "ready"
    assert prog_data["percentage"] == 100

    # 3. Ask question targeting calculate_total with deterministic Mock LLM
    qa_service = QAService(
        retrieval_manager=HybridRetrievalManager(storage_manager=index_storage_manager),
        llm_provider=MockLLMProvider(),
    )
    app.dependency_overrides[get_qa_service] = lambda: qa_service

    try:
        chat_resp = client.post(
            "/api/chat",
            json={
                "repo_id": repo_id,
                "question": "Where is calculate_total defined and what does it return?",
            },
        )
        assert chat_resp.status_code == 200
        chat_data = chat_resp.json()

        assert chat_data["abstained"] is False
        assert len(chat_data["citations"]) >= 1
        citation = chat_data["citations"][0]
        assert "src/orders.py" in citation["file_path"]
        assert citation["start_line"] >= 1
        assert citation["end_line"] >= citation["start_line"]
        assert "src/orders.py" in chat_data["answer"]
    finally:
        app.dependency_overrides.pop(get_qa_service, None)
        repo_manager.cleanup_repository(repo_id)


# ==============================================================================
# FLOW 2: Git URL Ingestion -> Index -> Question -> Citation
# ==============================================================================
def test_flow_2_git_url_to_citation(tmp_path: Path):
    """E2E Flow 2: Ingest public Git repository, index, ask question, verify line citations."""
    sample_git_url = "https://github.com/fastapi/sample-demo-repo"

    def fake_subprocess_run(cmd, capture_output, text, timeout, env, check):
        # Locate target_dir from cmd arguments
        dest_dir = Path(cmd[-1])
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / "routes.py").write_text(
            "from fastapi import APIRouter\n"
            "router = APIRouter()\n\n"
            "@router.get('/health')\n"
            "def health_check():\n"
            "    return {'status': 'healthy'}\n",
            encoding="utf-8",
        )
        (dest_dir / "README.md").write_text("# Demo API\nHealth route demo.", encoding="utf-8")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_subprocess_run), \
         patch("app.services.ingestion.git_validator.validate_git_url") as mock_val:
        mock_val.return_value = GitValidationResult(
            is_valid=True,
            normalized_url="https://github.com/fastapi/sample-demo-repo.git",
            repo_name="sample-demo-repo",
            host="github.com",
        )

        # 1. Ingest via Git
        git_resp = client.post(
            "/api/ingest/git",
            json={"url": sample_git_url},
        )
        assert git_resp.status_code == 201
        git_data = git_resp.json()
        repo_id = git_data["repo_id"]
        assert git_data["status"] == "ready"

        # 2. Check progress
        prog_resp = client.get(f"/api/ingest/progress/{repo_id}")
        assert prog_resp.status_code == 200
        assert prog_resp.json()["overall_status"] == "ready"

        # 3. Ask question
        qa_service = QAService(
            retrieval_manager=HybridRetrievalManager(storage_manager=index_storage_manager),
            llm_provider=MockLLMProvider(),
        )
        app.dependency_overrides[get_qa_service] = lambda: qa_service

        try:
            chat_resp = client.post(
                "/api/chat",
                json={
                    "repo_id": repo_id,
                    "question": "Which file defines health_check?",
                },
            )
            assert chat_resp.status_code == 200
            chat_data = chat_resp.json()
            assert chat_data["abstained"] is False
            assert len(chat_data["citations"]) >= 1
            assert "routes.py" in chat_data["citations"][0]["file_path"]
        finally:
            app.dependency_overrides.pop(get_qa_service, None)
            repo_manager.cleanup_repository(repo_id)


# ==============================================================================
# FLOW 3: Three Sequential Questions (Multi-Turn Conversation)
# ==============================================================================
def test_flow_3_three_sequential_multi_turn_questions(tmp_path: Path):
    """E2E Flow 3: Verify 3 consecutive questions maintain history without state loss."""
    repo_id = "multi-turn-e2e-repo"
    store = PersistentIndexStore(repo_id, custom_base_dir=tmp_path)

    chunk_db = CodeChunk(
        chunk_id="chk_db",
        repo_id=repo_id,
        file_path="src/database.py",
        start_line=1,
        end_line=25,
        content=(
            "import os\n"
            "from sqlalchemy import create_engine\n\n"
            "DATABASE_TIMEOUT = 30\n"
            "SSL_MODE = 'require'\n\n"
            "def get_db_engine():\n"
            "    db_url = os.getenv('DATABASE_URL')\n"
            "    return create_engine(db_url, timeout=DATABASE_TIMEOUT, connect_args={'sslmode': SSL_MODE})\n"
        ),
        symbol_name="get_db_engine",
        language="python",
        chunk_index=0,
        line_count=10,
        char_count=230,
    )
    vectors = [[0.1, 0.2, 0.3, 0.4]]
    store.save([chunk_db], vectors, "mock", "mock-model", 4)

    mock_storage = MagicMock()
    mock_storage.get_store.return_value = store
    retrieval_mgr = HybridRetrievalManager(storage_manager=mock_storage)
    qa_service = QAService(retrieval_manager=retrieval_mgr, llm_provider=MockLLMProvider())

    app.dependency_overrides[get_qa_service] = lambda: qa_service

    try:
        # Question 1: Initial query
        resp1 = client.post(
            "/api/chat",
            json={
                "repo_id": repo_id,
                "question": "Where is the database engine configured?",
                "conversation_history": [],
            },
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["abstained"] is False
        assert len(data1["citations"]) == 1
        assert data1["citations"][0]["file_path"] == "src/database.py"

        # Question 2: Follow-up referencing "that function"
        history = [
            {"role": "user", "content": "Where is the database engine configured?"},
            {"role": "assistant", "content": data1["answer"]},
        ]
        resp2 = client.post(
            "/api/chat",
            json={
                "repo_id": repo_id,
                "question": "What is the timeout parameter set to?",
                "conversation_history": history,
            },
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["abstained"] is False
        assert len(data2["citations"]) == 1
        assert data2["citations"][0]["file_path"] == "src/database.py"

        # Question 3: Third sequential question referencing SSL
        history.extend([
            {"role": "user", "content": "What is the timeout parameter set to?"},
            {"role": "assistant", "content": data2["answer"]},
        ])
        resp3 = client.post(
            "/api/chat",
            json={
                "repo_id": repo_id,
                "question": "Is SSL required for the connection?",
                "conversation_history": history,
            },
        )
        assert resp3.status_code == 200
        data3 = resp3.json()
        assert data3["abstained"] is False
        assert len(data3["citations"]) == 1
        assert data3["citations"][0]["file_path"] == "src/database.py"

    finally:
        app.dependency_overrides.pop(get_qa_service, None)


# ==============================================================================
# FLOW 4: Malformed and Adversarial Input Handling
# ==============================================================================
def test_flow_4_malformed_and_adversarial_inputs():
    """E2E Flow 4: Verify 400/404/422 responses with zero unhandled 500 crashes."""
    # 1. Empty question string -> 422
    resp_empty = client.post(
        "/api/chat",
        json={"repo_id": "valid_repo", "question": "   "},
    )
    assert resp_empty.status_code == 422

    # 2. Oversized question (> 2000 chars) -> 422
    resp_oversized = client.post(
        "/api/chat",
        json={"repo_id": "valid_repo", "question": "A" * 2050},
    )
    assert resp_oversized.status_code == 422

    # 3. Non-existent unindexed repo -> 404
    resp_unindexed = client.post(
        "/api/chat",
        json={"repo_id": "non_existent_random_repo_xyz", "question": "Where is the router?"},
    )
    assert resp_unindexed.status_code == 404

    # 4. Corrupt ZIP file -> 400
    corrupt_zip = b"NOT_A_VALID_ZIP_HEADER_CONTENT"
    resp_corrupt = client.post(
        "/api/ingest/zip",
        files={"file": ("broken.zip", io.BytesIO(corrupt_zip), "application/zip")},
    )
    assert resp_corrupt.status_code == 400
    assert "Corrupt or invalid ZIP" in resp_corrupt.json()["detail"]

    # 5. Invalid / Private SSRF Git URL -> 400
    resp_ssrf = client.post(
        "/api/ingest/git",
        json={"url": "http://169.254.169.254/latest/meta-data/"},
    )
    assert resp_ssrf.status_code == 400


# ==============================================================================
# FLOW 5: LLM Provider Failure Graceful Recovery
# ==============================================================================
def test_flow_5_llm_provider_failure_recovery(tmp_path: Path):
    """E2E Flow 5: Verify simulated provider errors map to clean HTTP responses without leaking secrets."""
    repo_id = "llm-recovery-repo"
    store = PersistentIndexStore(repo_id, custom_base_dir=tmp_path)
    chunk = CodeChunk(
        chunk_id="chk_rec",
        repo_id=repo_id,
        file_path="src/main.py",
        start_line=1,
        end_line=10,
        content="def run(): pass",
        language="python",
        chunk_index=0,
        line_count=2,
        char_count=16,
    )
    store.save([chunk], [[0.1, 0.2]], "mock", "mock-model", 2)

    mock_storage = MagicMock()
    mock_storage.get_store.return_value = store
    retrieval_mgr = HybridRetrievalManager(storage_manager=mock_storage)

    # 1. Rate Limit Error -> 429
    mock_llm_rl = MagicMock()
    mock_llm_rl.generate_response.side_effect = LLMRateLimitError(
        "Rate limit exceeded. Please wait 10 seconds."
    )
    qa_rl = QAService(retrieval_manager=retrieval_mgr, llm_provider=mock_llm_rl)
    app.dependency_overrides[get_qa_service] = lambda: qa_rl

    try:
        resp_rl = client.post(
            "/api/chat",
            json={"repo_id": repo_id, "question": "Explain run()"},
        )
        assert resp_rl.status_code == 429
        assert "rate limit" in resp_rl.json()["detail"].lower()

        # 2. Timeout Error -> 504
        mock_llm_to = MagicMock()
        mock_llm_to.generate_response.side_effect = LLMTimeoutError("LLM provider timed out after 60s")
        qa_to = QAService(retrieval_manager=retrieval_mgr, llm_provider=mock_llm_to)
        app.dependency_overrides[get_qa_service] = lambda: qa_to

        resp_to = client.post(
            "/api/chat",
            json={"repo_id": repo_id, "question": "Explain run()"},
        )
        assert resp_to.status_code == 504
        assert "timed out" in resp_to.json()["detail"].lower()

        # 3. Missing Key Configuration Error -> 503
        mock_llm_cfg = MagicMock()
        mock_llm_cfg.generate_response.side_effect = LLMConfigurationError(
            "LLM provider key missing or unconfigured"
        )
        qa_cfg = QAService(retrieval_manager=retrieval_mgr, llm_provider=mock_llm_cfg)
        app.dependency_overrides[get_qa_service] = lambda: qa_cfg

        resp_cfg = client.post(
            "/api/chat",
            json={"repo_id": repo_id, "question": "Explain run()"},
        )
        assert resp_cfg.status_code == 503
        assert "configured" in resp_cfg.json()["detail"].lower()
        # Ensure no tracebacks or secrets
        assert "Traceback" not in resp_cfg.text

    finally:
        app.dependency_overrides.pop(get_qa_service, None)
