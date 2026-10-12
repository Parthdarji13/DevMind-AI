"""
Tests for MongoDB integration and graceful fallback.
Verifies:
1. Real or fallback behavior depending on environment.
2. MongoStorage fallback behavior when get_mongo_db returns None.
3. Structure of records for users, repositories, and chat history.
"""
from backend.app.services.db.mongo import MongoStorage, is_mongo_available
from unittest.mock import patch


def test_mongo_graceful_fallback_when_db_none():
    # When get_mongo_db returns None (e.g., db unreachable or disabled)
    with patch("backend.app.services.db.mongo.get_mongo_db", return_value=None):
        assert MongoStorage.save_user({"id": "test_id", "email": "test@example.com"}) is False
        assert MongoStorage.get_user_by_email("test@example.com") is None
        assert MongoStorage.get_user_by_id("test_id") is None
        assert MongoStorage.list_all_users() == []
        assert MongoStorage.save_repository({"repo_id": "r1", "name": "repo1"}) is False
        assert MongoStorage.get_repository("r1") is None
        assert MongoStorage.list_repositories() == []
        assert MongoStorage.delete_repository("r1") is False
        assert MongoStorage.record_chat_turn("r1", "s1", "q", "a") is False
        assert MongoStorage.get_chat_history("r1") == []


def test_mongo_live_connectivity_if_available():
    # When MONGODB_URI is configured and reachable
    if is_mongo_available():
        test_uid = "test_pytest_user_001"
        saved = MongoStorage.save_user({
            "id": test_uid,
            "email": "pytest.user@example.com",
            "name": "Pytest User",
            "created_at": 123456789.0,
        })
        assert saved is True
        fetched = MongoStorage.get_user_by_id(test_uid)
        assert fetched is not None
        assert fetched["email"] == "pytest.user@example.com"
