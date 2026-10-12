"""
Lightweight, zero-dependency JWT token handler and User Authentication context.
Uses standard library HMAC-SHA256 for signing and verifying tokens.
Ref: PRD Section 17 & Security Architecture.
"""
import base64
import hashlib
import hmac
import json
import time
from typing import Optional
from fastapi import Header
from pydantic import BaseModel

from ...core.config import get_settings

settings = get_settings()


class UserContext(BaseModel):
    id: str
    email: str
    name: str
    picture: Optional[str] = None
    is_guest: bool = False


DEFAULT_GUEST_USER = UserContext(
    id="guest_default",
    email="guest@devmind.local",
    name="Guest Developer",
    picture=None,
    is_guest=True,
)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def create_access_token(
    user_id: str,
    email: str,
    name: str,
    picture: Optional[str] = None,
    is_guest: bool = False,
    expires_in_seconds: int = 86400 * 7,  # 7 days
) -> str:
    """Generates an HMAC-SHA256 signed JWT token."""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "picture": picture,
        "is_guest": is_guest,
        "iat": now,
        "exp": now + expires_in_seconds,
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

    key = settings.jwt_secret.encode("utf-8")
    signature = hmac.new(key, signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_access_token(token: str) -> Optional[dict]:
    """Validates signature and expiration of JWT token."""
    if not token or not isinstance(token, str):
        return None
    parts = token.strip().split(".")
    if len(parts) != 3:
        return None

    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    key = settings.jwt_secret.encode("utf-8")

    expected_sig = hmac.new(key, signing_input, hashlib.sha256).digest()
    try:
        provided_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, provided_sig):
            return None
        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        # Check expiration
        exp = payload.get("exp")
        if exp and int(time.time()) > exp:
            return None
        return payload
    except Exception:
        return None


def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> UserContext:
    """
    FastAPI dependency extracting user from Authorization: Bearer <token>.
    Falls back gracefully to Guest Developer context when no header is provided.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        data = decode_access_token(token)
        if data and "sub" in data:
            return UserContext(
                id=data["sub"],
                email=data.get("email", ""),
                name=data.get("name", "User"),
                picture=data.get("picture"),
                is_guest=data.get("is_guest", False),
            )

    return DEFAULT_GUEST_USER
