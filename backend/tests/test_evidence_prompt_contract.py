"""
Unit tests for evidence and prompt contract (Step 20).
Ref: PRD Section 6 (FR-07, FR-08, FR-09), Section 7, Section 8; Step 20 of execution guide.
Verifies:
- Only selected chunks are included in prompt context (bounded).
- System prompt enforces grounding, citations, [Inference], and abstention.
- Unsupported questions trigger abstention detection.
- Valid citations map back to evidence; invented/hallucinated citations are rejected.
- Inference tags [Inference] are properly recognized.
"""
import pytest

from backend.app.models.chat import ChatMessage, Citation
from backend.app.models.chunk import CodeChunk
from backend.app.services.llm.prompt import (
    SYSTEM_PROMPT,
    build_qa_prompt,
    extract_citations,
    format_chunk_context,
    has_inference,
    is_abstention,
    validate_citations_against_chunks,
)


def _make_chunk(
    chunk_id: str,
    file_path: str,
    start_line: int,
    end_line: int,
    content: str,
    symbol_name: str = None,
) -> CodeChunk:
    lines = content.splitlines() or [""]
    return CodeChunk(
        chunk_id=chunk_id,
        repo_id="test_repo",
        file_path=file_path,
        language="python",
        start_line=start_line,
        end_line=end_line,
        content=content,
        chunk_index=0,
        symbol_name=symbol_name,
        char_count=len(content),
        line_count=len(lines),
    )


def test_system_prompt_rules_enforcement():
    """Verify that system prompt explicitly mandates all 5 grounding rules."""
    assert "STRICT EVIDENCE BASE" in SYSTEM_PROMPT
    assert "CITATION REQUIREMENT" in SYSTEM_PROMPT
    assert "[File: <file_path>, Lines: <start_line>-<end_line>]" in SYSTEM_PROMPT
    assert "INFERENCE SEPARATION" in SYSTEM_PROMPT
    assert "[Inference]" in SYSTEM_PROMPT
    assert "ABSTENTION RULE" in SYSTEM_PROMPT
    assert "does not contain" in SYSTEM_PROMPT.lower()
    assert "CODE INTEGRITY" in SYSTEM_PROMPT


def test_only_selected_chunks_in_context():
    """Verify only the provided selected chunks appear in prompt, bounded by delimiters."""
    c1 = _make_chunk("chk_1", "src/auth.py", 10, 20, "def login(): pass", symbol_name="login")
    c2 = _make_chunk("chk_2", "src/db.py", 5, 15, "def connect(): pass", symbol_name="connect")

    chunks = [c1, c2]
    context = format_chunk_context(chunks)

    # Both selected chunks must be present
    assert "=== EVIDENCE CHUNK 1 [ID: chk_1] ===" in context
    assert "File: src/auth.py" in context
    assert "Lines: 10-20" in context
    assert "Symbol: login" in context
    assert "=== EVIDENCE CHUNK 2 [ID: chk_2] ===" in context
    assert "File: src/db.py" in context

    # Unrelated files must NOT be present
    assert "src/payment.py" not in context


def test_context_budget_capping():
    """Verify format_chunk_context stops adding chunks when max_total_chars is exceeded."""
    c1 = _make_chunk("chk_1", "file1.py", 1, 10, "A" * 200)
    c2 = _make_chunk("chk_2", "file2.py", 1, 10, "B" * 200)
    c3 = _make_chunk("chk_3", "file3.py", 1, 10, "C" * 200)

    # Budget of 350 chars fits 1 block (~280 chars), but cuts off the second
    context = format_chunk_context([c1, c2, c3], max_total_chars=350)
    assert "chk_1" in context
    assert "chk_3" not in context


def test_build_qa_prompt_assembly():
    """Verify build_qa_prompt puts together repository, history, evidence, and question."""
    c1 = _make_chunk("chk_1", "app/main.py", 1, 5, "app = FastAPI()")
    history = [
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="How can I assist with this codebase?"),
    ]

    sys_prompt, user_prompt = build_qa_prompt(
        question="Where is FastAPI initialized?",
        chunks=[c1],
        history=history,
        repo_name="my-fastapi-service",
    )

    assert sys_prompt == SYSTEM_PROMPT
    assert "REPOSITORY CONTEXT: my-fastapi-service" in user_prompt
    assert "USER: Hello" in user_prompt
    assert "ASSISTANT: How can I assist" in user_prompt
    assert "DEVELOPER QUESTION:\nWhere is FastAPI initialized?" in user_prompt
    assert "=== EVIDENCE CHUNK 1 [ID: chk_1] ===" in user_prompt


def test_abstention_detection():
    """Verify abstention detector identifies unsupported question responses."""
    unsupported_answer = (
        "The retrieved codebase evidence does not contain information about "
        "Kubernetes deployment or helm charts."
    )
    supported_answer = (
        "FastAPI is initialized in [File: app/main.py, Lines: 1-5]."
    )

    assert is_abstention(unsupported_answer) is True
    assert is_abstention("There is insufficient evidence to determine database retention policy.") is True
    assert is_abstention(supported_answer) is False


def test_inference_detection():
    """Verify detection of [Inference] markers."""
    answer_with_inference = (
        "The authentication endpoint is located in [File: auth.py, Lines: 10-25].\n"
        "[Inference] The codebase appears to follow a Clean Architecture pattern."
    )
    direct_answer = (
        "The authentication endpoint returns a JWT token [File: auth.py, Lines: 20-25]."
    )

    assert has_inference(answer_with_inference) is True
    assert has_inference(direct_answer) is False


def test_citation_extraction_and_validation():
    """Verify citations are extracted and validated against chunks, rejecting hallucinated files."""
    chunk = _make_chunk(
        chunk_id="chk_auth",
        file_path="backend/app/auth.py",
        start_line=10,
        end_line=30,
        content="def verify_token(token: str):\n    payload = jwt.decode(token)\n    return payload",
    )

    answer_text = (
        "Tokens are verified in [File: backend/app/auth.py, Lines: 10-20]. "
        "Also, billing is handled in [File: backend/app/billing.py, Lines: 1-5]."  # Hallucinated file!
    )

    extracted = extract_citations(answer_text)
    assert len(extracted) == 2
    assert extracted[0].file_path == "backend/app/auth.py"
    assert extracted[0].start_line == 10
    assert extracted[0].end_line == 20

    # Validate against actual evidence chunks
    validated = validate_citations_against_chunks(extracted, [chunk])

    # Only the genuine chunk should survive validation
    assert len(validated) == 1
    assert validated[0].file_path == "backend/app/auth.py"
    assert validated[0].chunk_id == "chk_auth"
    assert validated[0].snippet is not None
    assert "def verify_token" in validated[0].snippet

    # The hallucinated billing.py file must be completely rejected
    assert all(c.file_path != "backend/app/billing.py" for c in validated)
