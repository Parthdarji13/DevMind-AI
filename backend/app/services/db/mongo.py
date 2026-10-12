"""
MongoDB Database Service for DevMind AI.
Provides persistent cloud or local storage for:
1. User Accounts (Signups, profiles, passwords)
2. Repositories Metadata (Uploaded repos, owner IDs, file stats)
3. Chat History (User questions, AI answers, citations, timestamps)

Gracefully falls back to local JSON storage if MONGODB_URI is not configured.
"""
import logging
from typing import Optional, Any
from datetime import datetime, timezone

from ...core.config import get_settings

logger = logging.getLogger(__name__)

_mongo_client = None
_mongo_db = None
_has_logged_status = False


def get_mongo_db():
    """Lazily initializes and returns the MongoDB database instance if configured."""
    global _mongo_client, _mongo_db, _has_logged_status
    settings = get_settings()

    if not settings.mongodb_uri:
        return None

    if _mongo_db is not None:
        return _mongo_db

    try:
        from pymongo import MongoClient

        # Connect with 4-second timeout to avoid blocking startup if network is unavailable
        _mongo_client = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=4000,
            connectTimeoutMS=4000,
            socketTimeoutMS=4000,
        )
        # Test connection ping
        _mongo_client.admin.command("ping")
        _mongo_db = _mongo_client[settings.mongodb_db_name]

        if not _has_logged_status:
            logger.info(f"MongoDB connected successfully! Using database: '{settings.mongodb_db_name}'")
            _has_logged_status = True
        return _mongo_db
    except Exception as e:
        logger.warning(f"Could not connect to MongoDB ({settings.mongodb_uri[:20]}...): {e}. Falling back to local disk storage.")
        _mongo_client = None
        _mongo_db = None
        return None


def is_mongo_available() -> bool:
    """Returns True if MongoDB is configured and reachable."""
    return get_mongo_db() is not None


class MongoStorage:
    """High-level persistence helpers for users, repositories, and chat history."""

    @staticmethod
    def save_user(user_dict: dict[str, Any]) -> bool:
        """Upserts a user record in the 'users' collection."""
        db = get_mongo_db()
        if db is None:
            return False
        try:
            db.users.update_one(
                {"id": user_dict["id"]},
                {"$set": user_dict},
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error(f"MongoDB save_user failed: {e}")
            return False

    @staticmethod
    def get_user_by_email(email: str) -> Optional[dict[str, Any]]:
        db = get_mongo_db()
        if db is None:
            return None
        try:
            return db.users.find_one({"email": email.strip().lower()}, {"_id": 0})
        except Exception as e:
            logger.error(f"MongoDB get_user_by_email failed: {e}")
            return None

    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[dict[str, Any]]:
        db = get_mongo_db()
        if db is None:
            return None
        try:
            return db.users.find_one({"id": user_id}, {"_id": 0})
        except Exception as e:
            logger.error(f"MongoDB get_user_by_id failed: {e}")
            return None

    @staticmethod
    def list_all_users() -> list[dict[str, Any]]:
        db = get_mongo_db()
        if db is None:
            return []
        try:
            return list(db.users.find({}, {"_id": 0}))
        except Exception as e:
            logger.error(f"MongoDB list_all_users failed: {e}")
            return []

    # --- Repositories ---

    @staticmethod
    def save_repository(repo_dict: dict[str, Any]) -> bool:
        """Upserts repository metadata in the 'repositories' collection."""
        db = get_mongo_db()
        if db is None:
            return False
        try:
            db.repositories.update_one(
                {"repo_id": repo_dict["repo_id"]},
                {"$set": repo_dict},
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error(f"MongoDB save_repository failed: {e}")
            return False

    @staticmethod
    def get_repository(repo_id: str) -> Optional[dict[str, Any]]:
        db = get_mongo_db()
        if db is None:
            return None
        try:
            return db.repositories.find_one({"repo_id": repo_id}, {"_id": 0})
        except Exception as e:
            logger.error(f"MongoDB get_repository failed: {e}")
            return None

    @staticmethod
    def list_repositories(owner_id: Optional[str] = None) -> list[dict[str, Any]]:
        db = get_mongo_db()
        if db is None:
            return []
        try:
            query = {}
            if owner_id:
                query = {"$or": [{"owner_id": owner_id}, {"owner_id": None}]}
            return list(db.repositories.find(query, {"_id": 0}))
        except Exception as e:
            logger.error(f"MongoDB list_repositories failed: {e}")
            return []

    @staticmethod
    def delete_repository(repo_id: str) -> bool:
        db = get_mongo_db()
        if db is None:
            return False
        try:
            db.repositories.delete_one({"repo_id": repo_id})
            db.chat_history.delete_many({"repo_id": repo_id})
            return True
        except Exception as e:
            logger.error(f"MongoDB delete_repository failed: {e}")
            return False

    # --- Chat History ---

    @staticmethod
    def record_chat_turn(
        repo_id: str,
        session_id: str,
        user_message: str,
        assistant_message: str,
        citations: Optional[list[dict[str, Any]]] = None,
        user_id: Optional[str] = None,
        inference_detected: bool = False,
        abstained: bool = False,
    ) -> bool:
        """Records a completed chat question & answer turn in 'chat_history' collection."""
        db = get_mongo_db()
        if db is None:
            return False
        try:
            record = {
                "repo_id": repo_id,
                "session_id": session_id,
                "user_id": user_id,
                "user_message": user_message,
                "assistant_message": assistant_message,
                "citations": citations or [],
                "inference_detected": inference_detected,
                "abstained": abstained,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            db.chat_history.insert_one(record)
            return True
        except Exception as e:
            logger.error(f"MongoDB record_chat_turn failed: {e}")
            return False

    @staticmethod
    def get_chat_history(repo_id: str, session_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Retrieves recorded chat turns for a repository or session."""
        db = get_mongo_db()
        if db is None:
            return []
        try:
            query: dict[str, Any] = {"repo_id": repo_id}
            if session_id:
                query["session_id"] = session_id
            return list(db.chat_history.find(query, {"_id": 0}).sort("timestamp", 1))
        except Exception as e:
            logger.error(f"MongoDB get_chat_history failed: {e}")
            return []

    # --- Feedback ---

    @staticmethod
    def record_feedback(feedback_data: dict[str, Any]) -> bool:
        """Records user answer feedback (thumbs up/down, wrong source, comment) in 'feedback' collection."""
        db = get_mongo_db()
        if db is None:
            return False
        try:
            data = dict(feedback_data)
            data["created_at"] = datetime.now(timezone.utc).isoformat()
            db.feedback.insert_one(data)
            return True
        except Exception as e:
            logger.error(f"MongoDB record_feedback failed: {e}")
            return False

    @staticmethod
    def list_feedback(repo_id: Optional[str] = None) -> list[dict[str, Any]]:
        db = get_mongo_db()
        if db is None:
            return []
        try:
            query = {"repo_id": repo_id} if repo_id else {}
            return list(db.feedback.find(query, {"_id": 0}).sort("created_at", -1))
        except Exception as e:
            logger.error(f"MongoDB list_feedback failed: {e}")
            return []

