"""
Pytest configuration for DevMind AI test suite.
Provides clean test environment isolation and automatic test user context for legacy functional unit tests.
Security and penetration tests in test_security_attacks.py and test_auth_and_repositories.py
run without auto-authentication to test genuine zero-trust security boundaries.
"""
import sys
import pytest
from backend.app.services.auth.jwt_handler import get_current_user as b_get_user, UserContext

TEST_LEGACY_USER = UserContext(
    id="test_owner",
    email="test@devmind.ai",
    name="Test Owner",
    picture=None,
    is_guest=False,
)


@pytest.fixture(autouse=True)
def auto_auth_for_legacy_tests(request):
    """
    Automatically injects authenticated test user context for non-security, non-auth functional tests.
    Leaves security attack and auth verification tests completely un-mocked.
    """
    node_id = request.node.nodeid.lower()
    if "security" in node_id or "auth" in node_id:
        yield
        return

    # Patch both module namespace variants ('backend.app.main' and 'app.main')
    from backend.app.main import app as backend_app
    try:
        from app.main import app as direct_app
        from app.services.auth.jwt_handler import get_current_user as d_get_user
    except Exception:
        direct_app = None
        d_get_user = None

    backend_app.dependency_overrides[b_get_user] = lambda: TEST_LEGACY_USER
    if d_get_user:
        backend_app.dependency_overrides[d_get_user] = lambda: TEST_LEGACY_USER
    if direct_app:
        direct_app.dependency_overrides[b_get_user] = lambda: TEST_LEGACY_USER
        if d_get_user:
            direct_app.dependency_overrides[d_get_user] = lambda: TEST_LEGACY_USER

    try:
        yield
    finally:
        backend_app.dependency_overrides.pop(b_get_user, None)
        if d_get_user:
            backend_app.dependency_overrides.pop(d_get_user, None)
        if direct_app:
            direct_app.dependency_overrides.pop(b_get_user, None)
            if d_get_user:
                direct_app.dependency_overrides.pop(d_get_user, None)
