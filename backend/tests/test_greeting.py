"""
Tests for personalized user greeting feature in chat and voice.
Fulfills user requirement:
When user says or types 'hii devmind' or 'hello', DevMind responds with 'Hii, {name/id}!'
"""
import pytest
from backend.app.services.llm.greeting import (
    is_pure_greeting,
    extract_greeting_prefix,
    extract_user_display_name,
    generate_greeting_response,
    is_hinglish_greeting,
)
from backend.app.models.chat import ChatRequest, VoiceChatRequest
from backend.app.services.llm.qa_service import QAService
from backend.app.services.auth.jwt_handler import UserContext


def test_greeting_detection():
    # Pure greetings
    assert is_pure_greeting("hii devmind")
    assert is_pure_greeting("hi devmind")
    assert is_pure_greeting("hello devmind")
    assert is_pure_greeting("hii")
    assert is_pure_greeting("hi")
    assert is_pure_greeting("hello")
    assert is_pure_greeting("hey devmind")
    assert is_pure_greeting("namaste")
    assert is_pure_greeting("kaise ho")
    assert is_pure_greeting("good morning devmind")

    # Non-pure greetings (questions)
    assert not is_pure_greeting("what does main.py do?")
    assert not is_pure_greeting("explain the authentication flow")


def test_extract_greeting_prefix():
    prefix = extract_greeting_prefix("hii devmind explain the project")
    assert prefix == "explain the project"

    prefix2 = extract_greeting_prefix("hello devmind, what is the architecture?")
    assert prefix2 == "what is the architecture?"

    assert extract_greeting_prefix("explain the project") is None


def test_user_display_name_resolution():
    # User object name provided
    assert extract_user_display_name(user_name="Parth Darji") == "Parth"
    assert extract_user_display_name(user_name="John Doe") == "John"

    # Email fallback
    assert extract_user_display_name(user_name=None, email="parth@gmail.com") == "Parth"

    # User ID fallback
    assert extract_user_display_name(user_name=None, email=None, user_id="parth_123") == "Parth_123"

    # Default fallback
    assert extract_user_display_name(user_name=None, email=None, user_id=None) == "Parth"


def test_greeting_response_generation():
    # Text chat English
    res_en = generate_greeting_response("Parth", is_voice=False, is_hinglish=False)
    assert "Hii, Parth!" in res_en
    assert "DevMind AI" in res_en

    # Voice English
    res_voice = generate_greeting_response("Parth", is_voice=True, is_hinglish=False)
    assert "Hii, Parth!" in res_voice

    # Voice Hinglish
    res_hinglish = generate_greeting_response("Parth", is_voice=True, is_hinglish=True)
    assert "Hii, Parth!" in res_hinglish
    assert "Kaise hain aap" in res_hinglish


def test_qa_service_pure_greeting_chat():
    qa = QAService()
    req = ChatRequest(
        repo_id="test_repo",
        question="hii devmind",
        user_name="Parth Darji",
    )
    user = UserContext(id="usr_parth", email="parth@example.com", name="Parth Darji")
    resp = qa.answer_question(req, user=user)

    assert not resp.abstained
    assert "Hii, Parth!" in resp.answer
    assert resp.retrieved_chunks_count == 0


def test_qa_service_pure_greeting_voice():
    qa = QAService()
    req = VoiceChatRequest(
        repo_id="test_repo",
        question="hello devmind",
        user_name="Parth Darji",
    )
    user = UserContext(id="usr_parth", email="parth@example.com", name="Parth Darji")
    resp = qa.answer_voice_question(req, user=user)

    assert "Hii, Parth!" in resp.answer
    assert resp.cited_files == []
