"""
Authentication API routes for DevMind AI.
Supports Email/Password Sign Up & Sign In, 1-Click Google OAuth, Guest/Dev mode, and Profile retrieval.
Ref: PRD Section 17 & Security Architecture.
"""
import json
import logging
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..core.config import get_settings
from ..services.auth.jwt_handler import (
    UserContext,
    create_access_token,
    get_current_user,
    _b64url_decode,
)
from ..services.auth.user_manager import user_manager

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/auth", tags=["auth"])


class GuestLoginRequest(BaseModel):
    session_id: Optional[str] = None


class SignUpRequest(BaseModel):
    email: str
    password: str
    name: str


class SignInRequest(BaseModel):
    email: str
    password: str


class GoogleAuthRequest(BaseModel):
    credential: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    google_id: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserContext


@router.post("/signup", response_model=AuthResponse)
def sign_up(req: SignUpRequest):
    """
    Registers a new user account with email, password, and name.
    Secured using salted PBKDF2-HMAC-SHA256 password hashing.
    """
    clean_email = req.email.strip().lower()
    if not clean_email or "@" not in clean_email or "." not in clean_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid email address.",
        )

    if len(req.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long.",
        )

    clean_name = req.name.strip()
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide your name.",
        )

    try:
        record = user_manager.register_user(
            email=clean_email,
            password=req.password,
            name=clean_name,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    token = create_access_token(
        user_id=record.id,
        email=record.email,
        name=record.name,
        picture=record.picture,
        is_guest=False,
    )

    user = UserContext(
        id=record.id,
        email=record.email,
        name=record.name,
        picture=record.picture,
        is_guest=False,
    )
    return AuthResponse(access_token=token, user=user)


@router.post("/signin", response_model=AuthResponse)
def sign_in(req: SignInRequest):
    """
    Authenticates an existing user account using email and password.
    """
    clean_email = req.email.strip().lower()
    if not clean_email or not req.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required.",
        )

    record = user_manager.authenticate_user(clean_email, req.password)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(
        user_id=record.id,
        email=record.email,
        name=record.name,
        picture=record.picture,
        is_guest=False,
    )

    user = UserContext(
        id=record.id,
        email=record.email,
        name=record.name,
        picture=record.picture,
        is_guest=False,
    )
    return AuthResponse(access_token=token, user=user)


@router.post("/guest", response_model=AuthResponse)
def login_as_guest(req: Optional[GuestLoginRequest] = None):
    """
    Creates an instant guest session for local development or unauthenticated testing.
    Requires zero external configuration or cloud credentials.
    """
    sid = req.session_id if req and req.session_id else uuid.uuid4().hex[:8]
    user_id = f"guest_{sid}"
    email = f"{user_id}@devmind.local"
    name = f"Guest Dev ({sid[:4]})"

    token = create_access_token(
        user_id=user_id,
        email=email,
        name=name,
        picture=None,
        is_guest=True,
    )

    user = UserContext(
        id=user_id,
        email=email,
        name=name,
        picture=None,
        is_guest=True,
    )
    return AuthResponse(access_token=token, user=user)


@router.post("/google", response_model=AuthResponse)
def login_with_google(req: GoogleAuthRequest):
    """
    Seamless Google OAuth login.
    Supports either standard Google credential JWT or 1-click Google Profile authorization.
    """
    email = None
    name = None
    picture = None
    google_id = None

    if req.credential and req.credential.strip():
        # Parse Google Identity Services ID token JWT
        parts = req.credential.strip().split(".")
        if len(parts) == 3:
            try:
                payload_bytes = _b64url_decode(parts[1])
                payload = json.loads(payload_bytes.decode("utf-8"))
                email = payload.get("email")
                name = payload.get("name")
                picture = payload.get("picture")
                google_id = payload.get("sub")
            except Exception as e:
                logger.error(f"Failed to decode Google credential payload: {e}")

    # Fallback to direct parameters from OAuth consent
    if not email:
        email = req.email
        name = req.name
        picture = req.picture
        google_id = req.google_id

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google authorization failed: email address not provided.",
        )

    clean_email = email.strip().lower()
    clean_name = (name or clean_email.split("@")[0]).strip()

    record = user_manager.get_or_create_google_user(
        email=clean_email,
        name=clean_name,
        picture=picture,
        google_id=google_id,
    )

    token = create_access_token(
        user_id=record.id,
        email=record.email,
        name=record.name,
        picture=record.picture,
        is_guest=False,
    )

    user = UserContext(
        id=record.id,
        email=record.email,
        name=record.name,
        picture=record.picture,
        is_guest=False,
    )
    logger.info(f"User '{record.email}' ({record.id}) authenticated via Google.")
    return AuthResponse(access_token=token, user=user)


@router.get("/me", response_model=UserContext)
def get_current_user_profile(user: UserContext = Depends(get_current_user)):
    """Returns the authenticated user's profile and session status."""
    return user
