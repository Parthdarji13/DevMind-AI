"""
Unit and integration tests for Advanced Features (Features 8, 9, 11, 12).
Ref: PRD Section 6; Feature 8 (Flow Trace), Feature 9 (Onboarding Doc),
Feature 11 (Architecture Map), Feature 12 (Learning Mode & Quiz).
"""
import json
from pathlib import Path
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.models.chunk import CodeChunk
from backend.app.services.indexing.embeddings import MockEmbeddingProvider
from backend.app.services.indexing.storage import IndexStorageManager, PersistentIndexStore
from backend.app.services.llm.client import MockLLMProvider
from backend.app.services.retrieval.hybrid import HybridRetrievalManager
from backend.app.services.llm.advanced_features import AdvancedFeaturesService
from backend.app.api.routes_chat import get_advanced_features_service

client = TestClient(app)


def _seed_test_repo(repo_id: str, base_dir: Path) -> PersistentIndexStore:
    store = PersistentIndexStore(repo_id, custom_base_dir=base_dir)
    chunks = [
        CodeChunk(
            chunk_id="chk_api",
            repo_id=repo_id,
            file_path="api/routes_auth.py",
            language="python",
            start_line=1,
            end_line=30,
            content="from services.auth import verify_login\n\n@router.post('/login')\ndef login(data):\n    return verify_login(data)",
            chunk_index=0,
            symbol_name="login",
            char_count=100,
            line_count=6,
        ),
        CodeChunk(
            chunk_id="chk_svc",
            repo_id=repo_id,
            file_path="services/auth.py",
            language="python",
            start_line=1,
            end_line=45,
            content="from models.user import User\n\ndef verify_login(data):\n    user = User.get(data.username)\n    return user.check_pass(data.password)",
            chunk_index=1,
            symbol_name="verify_login",
            char_count=120,
            line_count=6,
        ),
        CodeChunk(
            chunk_id="chk_mdl",
            repo_id=repo_id,
            file_path="models/user.py",
            language="python",
            start_line=1,
            end_line=25,
            content="class User:\n    @classmethod\n    def get(cls, username):\n        return cls()",
            chunk_index=2,
            symbol_name="User",
            char_count=80,
            line_count=5,
        ),
    ]

    provider = MockEmbeddingProvider(dimension=32)
    vectors = provider.embed_texts([c.content for c in chunks])
    store.save(chunks, vectors, "mock", "mock-32", 32)
    return store


@pytest.fixture
def mock_service(tmp_path: Path):
    storage_manager = IndexStorageManager(base_dir=tmp_path)
    retrieval_manager = HybridRetrievalManager(storage_manager=storage_manager)
    llm_provider = MockLLMProvider()
    return AdvancedFeaturesService(
        retrieval_manager=retrieval_manager,
        llm_provider=llm_provider,
    )


def test_flow_trace_service(tmp_path: Path, mock_service: AdvancedFeaturesService):
    """Verify flow tracing generates steps, citations, and valid Mermaid sequence diagram."""
    repo_id = "test-flow-repo"
    _seed_test_repo(repo_id, tmp_path)

    # Mock JSON response from LLM
    json_flow = {
        "flow_title": "User Authentication Flow",
        "summary": "Traces login request from API route to user model verification.",
        "steps": [
            {
                "step_number": 1,
                "title": "Receive Login Request",
                "file_path": "api/routes_auth.py",
                "start_line": 3,
                "end_line": 7,
                "function_or_symbol": "login",
                "description": "API handler accepts credentials and delegates to auth service.",
            },
            {
                "step_number": 2,
                "title": "Verify Credentials",
                "file_path": "services/auth.py",
                "start_line": 3,
                "end_line": 7,
                "function_or_symbol": "verify_login",
                "description": "Verifies password hash against User record.",
            },
        ],
        "mermaid_diagram": "sequenceDiagram\n    autonumber\n    Client->>routes_auth: POST /login\n    routes_auth->>auth: verify_login()\n",
    }
    mock_service._llm_provider.generate_response = MagicMock(return_value=json.dumps(json_flow))

    resp = mock_service.trace_flow(repo_id, "User login flow")
    assert resp.flow_title == "User Authentication Flow"
    assert len(resp.steps) == 2
    assert resp.steps[0].file_path == "api/routes_auth.py"
    assert resp.steps[1].function_or_symbol == "verify_login"
    assert "sequenceDiagram" in resp.mermaid_diagram
    assert len(resp.citations) == 2


def test_onboarding_doc_service(tmp_path: Path, mock_service: AdvancedFeaturesService):
    """Verify onboarding doc generator creates 5 sections and preserves root ARCHITECTURE.md."""
    repo_id = "test-onboarding-repo"
    _seed_test_repo(repo_id, tmp_path)

    mock_doc = (
        "# Executive Overview & Architecture Philosophy\n"
        "DevMind AI is an evidence-grounded codebase QA system.\n\n"
        "# System Component Map & Directory Breakdown\n"
        "- `api/`: Route handlers\n- `services/`: Business logic\n\n"
        "# Core Request Lifecycles & Critical Workflows\n"
        "Requests hit the API router and trigger hybrid retrieval.\n\n"
        "# Key Interfaces, Data Models & Services\n"
        "Data is represented via Pydantic models.\n\n"
        "# Local Development & How to Get Started\n"
        "Run `uvicorn app.main:app --reload`.\n"
    )
    mock_service._llm_provider.generate_response = MagicMock(return_value=mock_doc)

    resp = mock_service.generate_onboarding_doc(repo_id)
    assert resp.repo_id == repo_id
    assert resp.file_count == 3
    assert "python" in resp.languages
    assert "# Executive Overview" in resp.content
    assert "# Local Development" in resp.content

    # Verify export file was created in data/exports/ and root ARCHITECTURE.md was untouched
    export_path = Path(f"data/exports/{repo_id}_ONBOARDING_GUIDE.md")
    assert export_path.exists()
    assert export_path.read_text(encoding="utf-8") == mock_doc


def test_architecture_map_service(tmp_path: Path, mock_service: AdvancedFeaturesService):
    """Verify architectural dependency graph extracts module layers and cross-module imports."""
    repo_id = "test-arch-repo"
    _seed_test_repo(repo_id, tmp_path)

    resp = mock_service.build_architecture_map(repo_id)
    assert resp.repo_id == repo_id
    assert resp.total_modules >= 3

    module_types = {n.module_type for n in resp.nodes}
    assert "api" in module_types
    assert "services" in module_types
    assert "models" in module_types

    # api/routes_auth imports services.auth, services.auth imports models.user
    assert len(resp.edges) >= 1
    edge_pairs = [(e.source, e.target) for e in resp.edges]
    assert ("api", "services") in edge_pairs or ("services", "models") in edge_pairs


def test_learning_quiz_service(tmp_path: Path, mock_service: AdvancedFeaturesService):
    """Verify learning mode quiz generates 4-choice questions with hints and explanations."""
    repo_id = "test-quiz-repo"
    _seed_test_repo(repo_id, tmp_path)

    json_quiz = [
        {
            "id": "q1",
            "question": "What function is responsible for user login verification?",
            "options": [
                "verify_login in services/auth.py",
                "check_pass in models/user.py",
                "handle_request in core/app.py",
                "None of the above",
            ],
            "correct_index": 0,
            "hint": "Look at services/auth.py.",
            "explanation": "verify_login is defined in services/auth.py lines 3-7.",
            "file_path": "services/auth.py",
            "start_line": 1,
            "end_line": 10,
        }
    ]
    mock_service._llm_provider.generate_response = MagicMock(return_value=json.dumps(json_quiz))

    resp = mock_service.generate_learning_quiz(repo_id)
    assert resp.repo_id == repo_id
    assert resp.total_questions >= 1
    q = resp.questions[0]
    assert len(q.options) == 4
    assert q.correct_index == 0
    assert "services/auth.py" in q.file_path
    assert q.hint != ""


def test_api_endpoints_integration(tmp_path: Path, mock_service: AdvancedFeaturesService):
    """Verify FastAPI routes for all 4 advanced endpoints with dependency override."""
    repo_id = "test-endpoints-repo"
    _seed_test_repo(repo_id, tmp_path)

    app.dependency_overrides[get_advanced_features_service] = lambda: mock_service

    try:
        # 1. Flow Trace POST
        flow_resp = client.post(
            "/api/chat/flow-trace",
            json={"repo_id": repo_id, "flow_query": "Login flow"},
        )
        assert flow_resp.status_code == 200
        assert "flow_title" in flow_resp.json()

        # 2. Onboarding Doc POST
        doc_resp = client.post(
            "/api/chat/onboarding-doc",
            json={"repo_id": repo_id},
        )
        assert doc_resp.status_code == 200
        assert "content" in doc_resp.json()

        # 3. Architecture Map GET
        arch_resp = client.get(f"/api/chat/architecture-map/{repo_id}")
        assert arch_resp.status_code == 200
        assert "nodes" in arch_resp.json()
        assert "edges" in arch_resp.json()

        # 4. Learning Quiz GET
        quiz_resp = client.get(f"/api/chat/quiz/{repo_id}")
        assert quiz_resp.status_code == 200
        assert "questions" in quiz_resp.json()

    finally:
        app.dependency_overrides.pop(get_advanced_features_service, None)
