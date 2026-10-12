"""
Tests for Authentication (Google OAuth + Guest mode) and Repository Management (List, Delete, Re-index).
"""
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app
from app.services.auth.jwt_handler import (
    create_access_token,
    decode_access_token,
    UserContext,
)
from app.services.ingestion.repository_manager import repo_manager
from app.models.repository import SourceType

client = TestClient(app)


def test_jwt_token_creation_and_validation():
    token = create_access_token(
        user_id="user_123",
        email="test@example.com",
        name="Test User",
        is_guest=False,
    )
    assert token is not None

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user_123"
    assert payload["email"] == "test@example.com"
    assert payload["name"] == "Test User"
    assert payload["is_guest"] is False


def test_jwt_tampered_signature_rejected():
    token = create_access_token(user_id="u1", email="u1@test.com", name="U1")
    parts = token.split(".")
    # Tamper payload
    tampered = f"{parts[0]}.eyJuZXdfZGF0YSI6IDF9.{parts[2]}"
    assert decode_access_token(tampered) is None


def test_guest_login_endpoint():
    resp = client.post("/api/auth/guest", json={"session_id": "demo123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["is_guest"] is True
    assert "demo123" in data["user"]["id"]


def test_auth_me_endpoint_with_and_without_token():
    # Without token -> defaults to guest
    resp_no_auth = client.get("/api/auth/me")
    assert resp_no_auth.status_code == 200
    assert resp_no_auth.json()["is_guest"] is True

    # With valid token
    token = create_access_token(user_id="john_doe", email="john@example.com", name="John")
    resp_auth = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_auth.status_code == 200
    assert resp_auth.json()["id"] == "john_doe"
    assert resp_auth.json()["email"] == "john@example.com"


def test_repository_user_isolation_and_management():
    token_user_a = create_access_token(user_id="user_a", email="a@devmind.ai", name="User A")
    token_user_b = create_access_token(user_id="user_b", email="b@devmind.ai", name="User B")

    # User A creates a repo
    repo_a = repo_manager.create_repository(
        name="repo_a_project",
        source_type=SourceType.ZIP,
        owner_id="user_a",
    )

    # User B creates a repo
    repo_b = repo_manager.create_repository(
        name="repo_b_project",
        source_type=SourceType.ZIP,
        owner_id="user_b",
    )

    # Listing as User A
    resp_a = client.get(
        "/api/repositories",
        headers={"Authorization": f"Bearer {token_user_a}"},
    )
    assert resp_a.status_code == 200
    repos_a = [r["repo_id"] for r in resp_a.json()]
    assert repo_a.repo_id in repos_a
    assert repo_b.repo_id not in repos_a

    # User B cannot delete User A's repo
    del_resp_unauthorized = client.delete(
        f"/api/repositories/{repo_a.repo_id}",
        headers={"Authorization": f"Bearer {token_user_b}"},
    )
    assert del_resp_unauthorized.status_code == 403

    # User A deletes their own repo
    del_resp_ok = client.delete(
        f"/api/repositories/{repo_a.repo_id}",
        headers={"Authorization": f"Bearer {token_user_a}"},
    )
    assert del_resp_ok.status_code == 200
    assert del_resp_ok.json()["status"] == "deleted"

    # Cleanup repo_b
    repo_manager.cleanup_repository(repo_b.repo_id)


def test_signup_and_signin_flow():
    import uuid
    test_email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    test_pass = "supersecret123"
    test_name = "Dev Mind User"

    # 1. Sign up
    signup_resp = client.post(
        "/api/auth/signup",
        json={"email": test_email, "password": test_pass, "name": test_name},
    )
    assert signup_resp.status_code == 200
    signup_data = signup_resp.json()
    assert signup_data["user"]["email"] == test_email
    assert signup_data["user"]["name"] == test_name
    assert "access_token" in signup_data

    # 2. Duplicate signup fails with 409
    dup_resp = client.post(
        "/api/auth/signup",
        json={"email": test_email, "password": test_pass, "name": test_name},
    )
    assert dup_resp.status_code == 409

    # 3. Sign in with correct credentials
    signin_resp = client.post(
        "/api/auth/signin",
        json={"email": test_email, "password": test_pass},
    )
    assert signin_resp.status_code == 200
    assert signin_resp.json()["user"]["email"] == test_email

    # 4. Sign in with wrong password fails with 401
    bad_pass_resp = client.post(
        "/api/auth/signin",
        json={"email": test_email, "password": "wrongpassword"},
    )
    assert bad_pass_resp.status_code == 401

