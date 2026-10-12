"""
Authentication API routes for DevMind AI.
Enforces genuine Google ID token verification via Google OAuth2 tokeninfo API.
Guarantees password complexity, brute force rate-limiting, and server-generated guest sessions.
Ref: PRD Section 17 & Security Architecture.
"""
import logging
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
import httpx
from pydantic import BaseModel

from ..core.config import get_settings
from ..services.auth.jwt_handler import (
    UserContext,
    create_access_token,
    get_current_user,
)
from ..services.auth.user_manager import user_manager

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignUpRequest(BaseModel):
    email: str
    password: str
    name: str


class SignInRequest(BaseModel):
    email: str
    password: str


class GoogleAuthRequest(BaseModel):
    credential: str  # Real Google ID Token (JWT) issued by Google Identity Services


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserContext


@router.post("/signup", response_model=AuthResponse)
def sign_up(req: SignUpRequest):
    """
    Registers a new user account with email, password, and name.
    Requires minimum 8-character password and enforces 600,000 PBKDF2 iterations.
    """
    clean_email = req.email.strip().lower()
    if not clean_email or "@" not in clean_email or "." not in clean_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid email address.",
        )

    if len(req.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
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
    Authenticates an existing user account with email and password.
    Includes brute force protection (locks out after 5 failed attempts).
    """
    clean_email = req.email.strip().lower()
    if not clean_email or not req.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required.",
        )

    try:
        record = user_manager.authenticate_user(clean_email, req.password)
    except ValueError as e:
        # Brute force lockout triggered
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        ) from e

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
def login_as_guest():
    """
    Creates an isolated guest session.
    Server strictly generates a cryptographically random UUID to prevent session hijacking.
    """
    sid = uuid.uuid4().hex[:12]
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
    Cryptographically verifies Google ID Token against Google's OAuth2 API.
    Fails closed if GOOGLE_CLIENT_ID is not configured.
    Rejects forged tokens, unverified emails, and mismatched audience IDs.
    """
    # 1. Fail closed if GOOGLE_CLIENT_ID is missing or placeholder
    client_id = (settings.google_client_id or "").strip()
    if not client_id or client_id.startswith("your_"):
        logger.error("Google authentication rejected: GOOGLE_CLIENT_ID is not configured on the server.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google authentication is not configured on this server.",
        )

    # 2. Enforce non-empty credential token
    credential = (req.credential or "").strip()
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google ID token credential is required.",
        )

    # 3. Cryptographically verify token with google-auth library
    google_data = None
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        request = google_requests.Request()
        google_data = id_token.verify_oauth2_token(credential, request, audience=client_id)
    except ValueError as ve:
        err_msg = str(ve).lower()
        if "audience" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google token audience does not match configured application client ID.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google authentication failed: {str(ve)}",
        )
    except Exception as g_err:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": credential})
            if resp.status_code == 200:
                google_data = resp.json()
            else:
                logger.warning(f"Google token verification rejected: {g_err}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Google authentication failed: Token signature or validity rejected by Google.",
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Google token verification error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google authentication failed: Invalid or forged Google ID token.",
            )

    # 4. Enforce audience match against configured Client ID
    token_aud = google_data.get("aud")
    if token_aud != client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google token audience does not match configured application client ID.",
        )

    # 5. Enforce email verification
    email_verified = google_data.get("email_verified")
    if email_verified not in (True, "true"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account email is not verified.",
        )

    email = google_data.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google token did not contain an email address.",
        )

    name = google_data.get("name") or email.split("@")[0]
    picture = google_data.get("picture")
    google_id = google_data.get("sub")

    record = user_manager.get_or_create_google_user(
        email=email,
        name=name,
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
    logger.info(f"Verified Google user '{record.email}' ({record.id}) successfully logged in.")
    return AuthResponse(access_token=token, user=user)


@router.get("/me", response_model=UserContext)
def get_current_user_profile(user: UserContext = Depends(get_current_user)):
    """Returns the authenticated user's profile and session status."""
    return user
