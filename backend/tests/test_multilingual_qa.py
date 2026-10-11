"""
Unit and integration tests for Hindi and Hinglish multilingual enhancement (Step 30).
Ref: Step 30 of execution guide; PRD Section 6 (FR-07, FR-08).
Verifies:
- Language detection accurately classifies English, Hinglish, and Hindi (Devanagari).
- Query expansion generates English retrieval variants for BM25 and vector search.
- Invariant: Code identifiers, filenames, paths, and API endpoints remain strictly in English.
- Citations format [File: <path>, Lines: <start>-<end>] remains exact and verifiable.
- Abstention detection works across English, Hinglish, and Hindi.
- QAService processes English, Hinglish, and Hindi questions with grounded citations.
"""
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from app.models.chat import ChatRequest
from app.models.chunk import CodeChunk
from app.services.indexing.storage import PersistentIndexStore
from app.services.llm.client import MockLLMProvider
from app.services.llm.prompt import (
    build_qa_prompt,
    extract_citations,
    is_abstention,
)
from app.services.llm.qa_service import QAService
from app.services.retrieval.hybrid import HybridRetrievalManager
from app.services.retrieval.multilingual import (
    detect_language,
    expand_multilingual_query,
    is_hindi_query,
    is_hinglish_query,
)


def test_language_detection():
    """Verify accurate detection of English, Hinglish, and Hindi Devanagari queries."""
    # English
    assert detect_language("How is user authentication handled?") == "english"
    assert detect_language("Where is the API router defined?") == "english"
    assert is_hindi_query("Where is the API router defined?") is False
    assert is_hinglish_query("Where is the API router defined?") is False

    # Hinglish
    assert detect_language("Is repo me user authentication kaise handle hota hai?") == "hinglish"
    assert detect_language("API routing aur endpoints kis file me defined hai?") == "hinglish"
    assert detect_language("Database connection kaha setup kiya gaya hai?") == "hinglish"
    assert is_hinglish_query("Ye function kya karta hai aur parameters kya hai?") is True

    # Hindi (Devanagari)
    assert detect_language("उपयोगकर्ता प्रमाणीकरण किस फ़ाइल में परिभाषित है?") == "hindi"
    assert detect_language("डेटाबेस कनेक्शन कहाँ सेट किया गया है?") == "hindi"
    assert is_hindi_query("यह कोड कैसे काम करता है?") is True


def test_query_expansion_generates_english_search_tokens():
    """Verify multilingual queries are augmented with English keywords for BM25 code indexing."""
    hinglish_q = "Is repo me user authentication kaise handle hota hai?"
    expanded_hinglish = expand_multilingual_query(hinglish_q)
    # Original query preserved
    assert hinglish_q in expanded_hinglish
    # Technical code tokens extracted
    assert "authentication" in expanded_hinglish
    assert "user" in expanded_hinglish

    hindi_q = "उपयोगकर्ता प्रमाणीकरण और डेटाबेस कनेक्शन कहाँ है?"
    expanded_hindi = expand_multilingual_query(hindi_q)
    assert hindi_q in expanded_hindi
    # Mapped technical tokens
    assert "authentication" in expanded_hindi or "auth" in expanded_hindi
    assert "database" in expanded_hindi or "db" in expanded_hindi

    # English query unchanged
    eng_q = "How does the router handle incoming requests?"
    assert expand_multilingual_query(eng_q) == eng_q


def test_abstention_detection_across_languages():
    """Verify is_abstention correctly flags missing evidence across English, Hinglish, and Hindi."""
    # English
    assert is_abstention("The retrieved codebase evidence does not contain information about billing.") is True
    assert is_abstention("There is insufficient evidence in the chunks.") is True

    # Hinglish
    assert is_abstention("Retrieved codebase evidence me user auth ke bare me jankari nahi hai.") is True
    assert is_abstention("Evidence me koi reference nahi mila.") is True

    # Hindi
    assert is_abstention("दिए गए कोडबेस साक्ष्य में इस प्रश्न की जानकारी उपलब्ध नहीं है।") is True
    assert is_abstention("कोडबेस में कोई संदर्भ नहीं मिला।") is True

    # Non-abstention positive responses
    assert is_abstention("The authentication logic is in [File: src/auth.ts, Lines: 10-25].") is False
    assert is_abstention("User authentication src/auth.ts [File: src/auth.ts, Lines: 1-10] me implement kiya gaya hai.") is False


def test_prompt_contract_preserves_code_identifiers_and_citation_syntax():
    """Verify build_qa_prompt instructs preserving code identifiers and citations in exact format."""
    chunks = [
        CodeChunk(
            chunk_id="chk_auth",
            repo_id="test_repo",
            file_path="src/lib/auth.ts",
            start_line=12,
            end_line=45,
            content="export function verifyJwtToken(token: string) { return true; }",
            chunk_index=0,
            symbol_name="verifyJwtToken",
            line_count=34,
            char_count=65,
            language="typescript",
        )
    ]

    # Hinglish Prompt
    sys_prompt, user_prompt_hinglish = build_qa_prompt(
        question="Is file me verifyJwtToken kaise kaam karta hai?",
        chunks=chunks,
    )
    assert "Hinglish" in user_prompt_hinglish
    assert "src/lib/auth.ts" in user_prompt_hinglish
    assert "verifyJwtToken" in user_prompt_hinglish
    assert "[File: <path>, Lines: <start>-<end>]" in user_prompt_hinglish

    # Hindi Prompt
    sys_prompt, user_prompt_hindi = build_qa_prompt(
        question="verifyJwtToken फ़ंक्शन कैसे काम करता है?",
        chunks=chunks,
    )
    assert "Hindi" in user_prompt_hindi
    assert "src/lib/auth.ts" in user_prompt_hindi


def test_qa_service_hinglish_and_hindi_grounded_qa(tmp_path: Path):
    """Integration test verifying QAService answers English, Hinglish, and Hindi with exact citations."""
    repo_id = "multilingual-test-repo"
    store = PersistentIndexStore(repo_id, custom_base_dir=tmp_path)

    chunks = [
        CodeChunk(
            chunk_id="c_login",
            repo_id=repo_id,
            file_path="src/api/auth/login.py",
            start_line=10,
            end_line=30,
            content="def handle_user_login(request):\n    # Authenticate credentials\n    return {'status': 'ok'}",
            symbol_name="handle_user_login",
            language="python",
            chunk_index=0,
            line_count=21,
            char_count=98,
        )
    ]
    vectors = [[0.1, 0.2, 0.3, 0.4]]
    store.save(chunks, vectors, provider_name="mock", model_name="mock-model", dimension=4)

    mock_storage = MagicMock()
    mock_storage.get_store.return_value = store
    retrieval_mgr = HybridRetrievalManager(storage_manager=mock_storage)

    qa = QAService(
        retrieval_manager=retrieval_mgr,
        llm_provider=MockLLMProvider(),
    )

    # 1. English Question
    req_en = ChatRequest(
        repo_id=repo_id,
        question="Where is handle_user_login implemented?",
    )
    resp_en = qa.answer_question(req_en)
    assert resp_en.abstained is False
    assert len(resp_en.citations) == 1
    assert resp_en.citations[0].file_path == "src/api/auth/login.py"
    assert resp_en.citations[0].start_line == 10
    assert resp_en.citations[0].end_line == 30
    assert "src/api/auth/login.py" in resp_en.answer

    # 2. Hinglish Question
    req_hinglish = ChatRequest(
        repo_id=repo_id,
        question="Is repo me user login aur handle_user_login kaise handle hota hai?",
    )
    resp_hinglish = qa.answer_question(req_hinglish)
    assert resp_hinglish.abstained is False
    assert len(resp_hinglish.citations) == 1
    assert resp_hinglish.citations[0].file_path == "src/api/auth/login.py"
    assert resp_hinglish.citations[0].start_line == 10
    assert resp_hinglish.citations[0].end_line == 30
    # Invariant: Code identifiers and paths remain exact in English
    assert "src/api/auth/login.py" in resp_hinglish.answer

    # 3. Hindi (Devanagari) Question
    req_hindi = ChatRequest(
        repo_id=repo_id,
        question="यूजर लॉगिन फ़ंक्शन handle_user_login किस फ़ाइल में परिभाषित है?",
    )
    resp_hindi = qa.answer_question(req_hindi)
    assert resp_hindi.abstained is False
    assert len(resp_hindi.citations) == 1
    assert resp_hindi.citations[0].file_path == "src/api/auth/login.py"
    assert resp_hindi.citations[0].start_line == 10
    assert resp_hindi.citations[0].end_line == 30
    # Invariant: Code identifiers and paths remain exact in English
    assert "src/api/auth/login.py" in resp_hindi.answer
