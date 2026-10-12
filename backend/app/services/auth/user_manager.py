"""
User account persistence, registration, and password hashing service.
Uses PBKDF2-HMAC-SHA256 for secure password storage with unique salts.
Ref: PRD Section 17 & Security Architecture.
"""
import binascii
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

from ...core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class UserRecord(BaseModel):
    id: str
    email: str
    name: str
    password_hash: Optional[str] = None
    picture: Optional[str] = None
    is_guest: bool = False
    created_at: float


def hash_password(password: str) -> str:
    """Hashes a password with a random 16-byte salt using PBKDF2-HMAC-SHA256."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return binascii.hexlify(salt).decode("ascii") + "$" + binascii.hexlify(dk).decode("ascii")


def verify_password(password: str, hashed_str: str) -> bool:
    """Verifies a password against a PBKDF2-HMAC-SHA256 hash."""
    if not hashed_str or "$" not in hashed_str:
        return False
    try:
        salt_hex, dk_hex = hashed_str.split("$")
        salt = binascii.unhexlify(salt_hex.encode("ascii"))
        expected_dk = binascii.unhexlify(dk_hex.encode("ascii"))
        computed_dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return hmac.compare_digest(expected_dk, computed_dk)
    except Exception:
        return False


class UserManager:
    def __init__(self):
        self._users: dict[str, UserRecord] = {}  # keyed by user_id
        self._email_index: dict[str, str] = {}  # email.lower() -> user_id
        self._load_users()

    def _get_storage_path(self) -> Path:
        settings.ensure_storage_dirs()
        return settings.data_dir / "users.json"

    def _load_users(self) -> None:
        path = self._get_storage_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for item in data:
                record = UserRecord(**item)
                self._users[record.id] = record
                self._email_index[record.email.lower()] = record.id
        except Exception as e:
            logger.error(f"Error loading users from {path}: {e}")

    def _save_users(self) -> None:
        path = self._get_storage_path()
        try:
            data = [u.model_dump() for u in self._users.values()]
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Error saving users to {path}: {e}")

    def register_user(self, email: str, password: str, name: str) -> UserRecord:
        clean_email = email.strip().lower()
        if clean_email in self._email_index:
            raise ValueError(f"An account with email '{clean_email}' already exists.")

        user_id = f"usr_{uuid.uuid4().hex[:12]}"
        record = UserRecord(
            id=user_id,
            email=clean_email,
            name=name.strip() or clean_email.split("@")[0],
            password_hash=hash_password(password),
            picture=None,
            is_guest=False,
            created_at=time.time(),
        )

        self._users[user_id] = record
        self._email_index[clean_email] = user_id
        self._save_users()
        logger.info(f"Registered new user account: {clean_email} ({user_id})")
        return record

    def authenticate_user(self, email: str, password: str) -> Optional[UserRecord]:
        clean_email = email.strip().lower()
        user_id = self._email_index.get(clean_email)
        if not user_id:
            return None
        record = self._users.get(user_id)
        if not record or not record.password_hash:
            return None
        if not verify_password(password, record.password_hash):
            return None
        return record

    def get_user_by_id(self, user_id: str) -> Optional[UserRecord]:
        return self._users.get(user_id)

    def get_user_by_email(self, email: str) -> Optional[UserRecord]:
        user_id = self._email_index.get(email.strip().lower())
        return self._users.get(user_id) if user_id else None

    def get_or_create_google_user(
        self,
        email: str,
        name: str,
        picture: Optional[str] = None,
        google_id: Optional[str] = None,
    ) -> UserRecord:
        clean_email = email.strip().lower()
        existing_id = self._email_index.get(clean_email)
        if existing_id and existing_id in self._users:
            record = self._users[existing_id]
            if picture and not record.picture:
                record.picture = picture
                self._save_users()
            return record

        user_id = f"google_{google_id}" if google_id else f"usr_{uuid.uuid4().hex[:12]}"
        record = UserRecord(
            id=user_id,
            email=clean_email,
            name=name.strip() or clean_email.split("@")[0],
            password_hash=None,
            picture=picture,
            is_guest=False,
            created_at=time.time(),
        )
        self._users[user_id] = record
        self._email_index[clean_email] = user_id
        self._save_users()
        return record


# Global singleton instance
user_manager = UserManager()
