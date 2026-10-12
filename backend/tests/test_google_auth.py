"""
Unit and integration tests for Google Authentication in DevMind AI.
Tests fulfill Requirement 7:
- Missing Client ID (fail-closed behavior)
- Missing credentials
- Invalid or forged tokens
- Incorrect audience mismatch
- Unverified emails
- Successful genuine Google authentication flow
"""
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.api import routes_auth

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Missing Client ID (Fail-Closed)
# ---------------------------------------------------------------------------
def test_google_auth_missing_client_id_fails_closed(monkeypatch):
    """When GOOGLE_CLIENT_ID is empty or unset, Google auth must fail closed (HTTP 500)."""
    monkeypatch.setattr(routes_auth.settings, "google_client_id", "")
    resp = client.post("/api/auth/google", json={"credential": "sample_token"})
    assert resp.status_code == 500
    assert "Google authentication is not configured on this server" in resp.json()["detail"]


def test_google_auth_placeholder_client_id_fails_closed(monkeypatch):
    """When GOOGLE_CLIENT_ID is a template placeholder, Google auth must fail closed (HTTP 500)."""
    monkeypatch.setattr(routes_auth.settings, "google_client_id", "your_google_oauth_client_id_here.apps.googleusercontent.com")
    resp = client.post("/api/auth/google", json={"credential": "sample_token"})
    assert resp.status_code == 500
    assert "Google authentication is not configured on this server" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 2. Missing or Empty Credentials
# ---------------------------------------------------------------------------
def test_google_auth_missing_credentials_rejected(monkeypatch):
    """When credential is empty or whitespace, return HTTP 400."""
    monkeypatch.setattr(routes_auth.settings, "google_client_id", "configured-id.apps.googleusercontent.com")

    # Empty string
    resp_empty = client.post("/api/auth/google", json={"credential": ""})
    assert resp_empty.status_code == 400
    assert "credential is required" in resp_empty.json()["detail"]

    # Whitespace
    resp_ws = client.post("/api/auth/google", json={"credential": "    "})
    assert resp_ws.status_code == 400

    # Missing field
    resp_none = client.post("/api/auth/google", json={})
    assert resp_none.status_code == 422


# ---------------------------------------------------------------------------
# 3. Invalid or Forged Tokens
# ---------------------------------------------------------------------------
def test_google_auth_invalid_tokens_rejected(monkeypatch):
    """When credential is malformed or invalid, return HTTP 401."""
    monkeypatch.setattr(routes_auth.settings, "google_client_id", "configured-id.apps.googleusercontent.com")

    resp = client.post("/api/auth/google", json={"credential": "invalid.bogus.jwt_signature"})
    assert resp.status_code == 401
    assert "Google authentication failed" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 4. Incorrect Audience
# ---------------------------------------------------------------------------
def test_google_auth_incorrect_audience_rejected(monkeypatch):
    """When token audience does not match configured GOOGLE_CLIENT_ID, return HTTP 401."""
    expected_client_id = "devmind-prod.apps.googleusercontent.com"
    monkeypatch.setattr(routes_auth.settings, "google_client_id", expected_client_id)

    # Mock verify_oauth2_token returning token with different audience
    from google.oauth2 import id_token

    def mock_verify(*args, **kwargs):
        return {
            "sub": "g_1111",
            "email": "user@gmail.com",
            "name": "User",
            "email_verified": True,
            "aud": "different-client-id.apps.googleusercontent.com",
        }

    monkeypatch.setattr(id_token, "verify_oauth2_token", mock_verify)

    resp = client.post("/api/auth/google", json={"credential": "mock_id_token"})
    assert resp.status_code == 401
    assert "audience does not match configured application client ID" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 5. Unverified Email
# ---------------------------------------------------------------------------
def test_google_auth_unverified_email_rejected(monkeypatch):
    """When Google account email is not verified, return HTTP 401."""
    client_id = "devmind-app.apps.googleusercontent.com"
    monkeypatch.setattr(routes_auth.settings, "google_client_id", client_id)

    from google.oauth2 import id_token

    def mock_verify(*args, **kwargs):
        return {
            "sub": "g_2222",
            "email": "unverified@gmail.com",
            "name": "Unverified User",
            "email_verified": False,
            "aud": client_id,
        }

    monkeypatch.setattr(id_token, "verify_oauth2_token", mock_verify)

    resp = client.post("/api/auth/google", json={"credential": "mock_id_token"})
    assert resp.status_code == 401
    assert "Google account email is not verified" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 6. Missing Email in Token Payload
# ---------------------------------------------------------------------------
def test_google_auth_missing_email_in_token_rejected(monkeypatch):
    """When Google token does not contain an email address, return HTTP 401."""
    client_id = "devmind-app.apps.googleusercontent.com"
    monkeypatch.setattr(routes_auth.settings, "google_client_id", client_id)

    from google.oauth2 import id_token

    def mock_verify(*args, **kwargs):
        return {
            "sub": "g_3333",
            "name": "No Email User",
            "email_verified": True,
            "aud": client_id,
        }

    monkeypatch.setattr(id_token, "verify_oauth2_token", mock_verify)

    resp = client.post("/api/auth/google", json={"credential": "mock_id_token"})
    assert resp.status_code == 401
    assert "Google token did not contain an email address" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 7. Successful Google Login Flow
# ---------------------------------------------------------------------------
def test_google_auth_successful_login(monkeypatch):
    """Valid Google ID token issues a signed JWT and persists/fetches user account."""
    client_id = "devmind-official.apps.googleusercontent.com"
    monkeypatch.setattr(routes_auth.settings, "google_client_id", client_id)

    from google.oauth2 import id_token

    def mock_verify(*args, **kwargs):
        return {
            "sub": "g_999888777",
            "email": "verified.developer@gmail.com",
            "name": "Verified Developer",
            "picture": "https://lh3.googleusercontent.com/a/avatar123",
            "email_verified": True,
            "aud": client_id,
        }

    monkeypatch.setattr(id_token, "verify_oauth2_token", mock_verify)

    resp = client.post("/api/auth/google", json={"credential": "valid_signed_google_jwt"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "verified.developer@gmail.com"
    assert data["user"]["name"] == "Verified Developer"
    assert data["user"]["picture"] == "https://lh3.googleusercontent.com/a/avatar123"
    assert data["user"]["is_guest"] is False

    # Verify that the access token can be used to query /api/auth/me
    token = data["access_token"]
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "verified.developer@gmail.com"
    assert me_resp.json()["is_guest"] is False
