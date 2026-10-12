"""
Security and Penetration Testing Suite for DevMind AI.
Replicates real-world exploit attacks to verify zero-trust authentication,
Google OAuth cryptographic verification, per-user repository isolation,
JWT secret hardening, and brute-force protection.
"""
import base64
import hashlib
import hmac
import json
import time
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.models.repository import SourceType
from backend.app.services.auth.jwt_handler import create_access_token
from backend.app.services.ingestion.repository_manager import repo_manager

client = TestClient(app)


def _craft_forged_jwt(payload_dict: dict, secret_key: str) -> str:
    """Helper to craft an HMAC-SHA256 JWT using an arbitrary key."""
    header = {"alg": "HS256", "typ": "JWT"}
    h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).rstrip(b"=").decode()
    sig = hmac.new(secret_key.encode(), f"{h_b64}.{p_b64}".encode(), hashlib.sha256).digest()
    s_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    return f"{h_b64}.{p_b64}.{s_b64}"


# ---------------------------------------------------------------------------
# ATTACK 1: Raw Email Body Spoofing in Google Login
# ---------------------------------------------------------------------------
def test_attack_1_google_login_raw_email_body_rejected():
    """
    Attacker attempts to take over victim's account by sending only their email
    to /api/auth/google without a valid Google credential.
    """
    resp = client.post(
        "/api/auth/google",
        json={"email": "victim@company.com", "name": "Victim User"},
    )
    # Must reject because 'credential' field is required
    assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# ATTACK 2: Forged Google Token with Fake Signature
# ---------------------------------------------------------------------------
def test_attack_2_forged_google_token_with_fake_signature_rejected():
    """
    Attacker crafts a self-signed JWT claiming to be from Google with victim's email.
    """
    fake_payload = {
        "iss": "https://accounts.google.com",
        "sub": "google_123456789",
        "email": "victim@company.com",
        "email_verified": True,
        "name": "Victim User",
        "aud": "fake-client-id",
        "exp": int(time.time()) + 3600,
    }
    fake_token = _craft_forged_jwt(fake_payload, "attacker_arbitrary_signing_key")

    resp = client.post(
        "/api/auth/google",
        json={"credential": fake_token},
    )
    # Must reject with 401 Unauthorized
    assert resp.status_code == 401
    assert "Google authentication failed" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# ATTACK 3: Token Forgery using Leaked Default Secret Key
# ---------------------------------------------------------------------------
def test_attack_3_default_hardcoded_jwt_secret_rejected():
    """
    Attacker attempts to forge a DevMind access token using the old public default secret
    'devmind_ai_super_secret_jwt_key_2026'.
    """
    old_leaked_secret = "devmind_ai_super_secret_jwt_key_2026"
    forged_token = _craft_forged_jwt(
        {
            "sub": "victim_user_id",
            "email": "victim@company.com",
            "name": "Victim User",
            "is_guest": False,
            "iat": int(time.time()),
            "exp": int(time.time()) + 86400,
        },
        old_leaked_secret,
    )

    resp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {forged_token}"},
    )
    # Must reject forged token because server does not use old leaked secret
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# ATTACK 4: Unauthenticated Access to Chat Endpoint
# ---------------------------------------------------------------------------
def test_attack_4_unauthenticated_chat_rejected():
    """
    Attacker tries to query code or extract information without providing an auth token.
    """
    resp = client.post(
        "/api/chat",
        json={"repo_id": "any_repo_id", "question": "What are the API keys?"},
    )
    assert resp.status_code == 401
    assert "Authentication required" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# ATTACK 5: Cross-Tenant Access to Victim Repository via Chat
# ---------------------------------------------------------------------------
def test_attack_5_cross_tenant_chat_access_forbidden():
    """
    Attacker has their own valid account, but attempts to query a private repository
    belonging to a victim.
    """
    # 1. Register victim repo
    victim_repo = repo_manager.create_repository(
        name="victim-secret-repo",
        source_type=SourceType.ZIP,
        owner_id="victim_usr_001",
    )

    # 2. Attacker logs in with valid token
    attacker_token = create_access_token(
        user_id="attacker_usr_999",
        email="attacker@evil.com",
        name="Attacker",
    )

    # 3. Attacker targets victim's repository
    resp = client.post(
        "/api/chat",
        json={"repo_id": victim_repo.repo_id, "question": "Show passwords"},
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert resp.status_code == 403
    assert "Access denied" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# ATTACK 6: Unauthenticated Access to Repositories & Ingest Endpoints
# ---------------------------------------------------------------------------
def test_attack_6_unauthenticated_repo_endpoints_rejected():
    """
    Attacker tries to read repo status, progress, indexing, or suggestions without auth.
    """
    repo = repo_manager.create_repository(
        name="protected-repo",
        source_type=SourceType.GIT,
        owner_id="legit_owner_123",
    )
    rid = repo.repo_id

    # Status without token -> 401
    resp_status = client.get(f"/api/ingest/status/{rid}")
    assert resp_status.status_code == 401

    # Progress without token -> 401
    resp_prog = client.get(f"/api/ingest/progress/{rid}")
    assert resp_prog.status_code == 401

    # Index trigger without token -> 401
    resp_idx = client.post(f"/api/ingest/index/{rid}")
    assert resp_idx.status_code == 401

    # Suggested questions without token -> 401
    resp_sug = client.get(f"/api/chat/suggested-questions/{rid}")
    assert resp_sug.status_code == 401


# ---------------------------------------------------------------------------
# ATTACK 7: Cross-Tenant Delete and Reindex Attempts
# ---------------------------------------------------------------------------
def test_attack_7_cross_tenant_delete_and_reindex_forbidden():
    """
    Attacker tries to delete or reindex a repository belonging to another user.
    """
    victim_repo = repo_manager.create_repository(
        name="victim-important-app",
        source_type=SourceType.ZIP,
        owner_id="victim_corp",
    )
    rid = victim_repo.repo_id

    attacker_token = create_access_token(
        user_id="attacker_101",
        email="attacker@dark.web",
        name="Attacker",
    )

    # Try delete victim's repo
    resp_del = client.delete(
        f"/api/repositories/{rid}",
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert resp_del.status_code == 403

    # Try reindex victim's repo
    resp_reidx = client.post(
        f"/api/repositories/{rid}/reindex",
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert resp_reidx.status_code == 403


# ---------------------------------------------------------------------------
# ATTACK 8: Guest Session Hijacking Prevention
# ---------------------------------------------------------------------------
def test_attack_8_guest_session_hijacking_prevented():
    """
    Attacker tries to hijack an existing guest session by submitting a targeted session_id.
    Server must ignore client-provided session IDs and generate a random UUID.
    """
    resp = client.post(
        "/api/auth/guest",
        json={"session_id": "target_guest_session_007"},
    )
    assert resp.status_code == 200
    user_id = resp.json()["user"]["id"]
    assert user_id.startswith("guest_")
    assert "target_guest_session_007" not in user_id


# ---------------------------------------------------------------------------
# ATTACK 9: Brute-Force Password Guessing Lockout
# ---------------------------------------------------------------------------
def test_attack_9_brute_force_password_guessing_locked_out():
    """
    Attacker attempts 6 incorrect passwords in rapid succession.
    Account must trigger lockout after 5 failed attempts and return HTTP 429.
    """
    import uuid
    target_email = f"target_lockout_{uuid.uuid4().hex[:8]}@company.com"

    # Register victim account with strong password
    reg_resp = client.post(
        "/api/auth/signup",
        json={
            "email": target_email,
            "password": "CorrectHorseBatteryStaple123!",
            "name": "Target Account",
        },
    )
    assert reg_resp.status_code == 200

    # 5 failed password attempts
    for i in range(5):
        fail_resp = client.post(
            "/api/auth/signin",
            json={"email": target_email, "password": f"wrong_password_{i}"},
        )
        assert fail_resp.status_code == 401

    # 6th attempt should be blocked by brute-force protection
    lockout_resp = client.post(
        "/api/auth/signin",
        json={"email": target_email, "password": "wrong_password_6"},
    )
    assert lockout_resp.status_code == 429
    assert "locked for 5 minutes" in lockout_resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# ATTACK 10: Weak Password Registration Rejected
# ---------------------------------------------------------------------------
def test_attack_10_weak_password_registration_rejected():
    """
    Attacker tries to register an account with a password shorter than 8 characters.
    """
    import uuid
    weak_email = f"weak_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/auth/signup",
        json={"email": weak_email, "password": "short", "name": "Weak User"},
    )
    assert resp.status_code == 400
    assert "8 characters" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# ATTACK 11: Empty/Missing owner_id Repository is NOT Public
# ---------------------------------------------------------------------------
def test_attack_11_unowned_repository_not_public():
    """
    Verify that legacy or unassigned repositories with owner_id = None
    cannot be accessed or deleted by arbitrary users.
    """
    orphan_repo = repo_manager.create_repository(
        name="orphan-legacy-repo",
        source_type=SourceType.ZIP,
        owner_id=None,  # Empty owner
    )
    rid = orphan_repo.repo_id

    attacker_token = create_access_token(
        user_id="user_attacker_202",
        email="attacker@test.com",
        name="Attacker",
    )

    # Trying to delete unowned repo must be forbidden
    resp_del = client.delete(
        f"/api/repositories/{rid}",
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert resp_del.status_code == 403

    # Trying to reindex unowned repo must be forbidden
    resp_reidx = client.post(
        f"/api/repositories/{rid}/reindex",
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert resp_reidx.status_code == 403
