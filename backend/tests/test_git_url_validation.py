"""
Unit tests for Public Git URL validation and SSRF mitigation (Step 10).
"""
import sys
from pathlib import Path
import pytest

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.ingestion.git_validator import (
    validate_git_url,
    InvalidGitProtocolError,
    EmbeddedCredentialsError,
    SSRFBlockedError,
    MalformedGitUrlError,
)


def test_valid_public_git_urls():
    # Test valid GitHub and GitLab repositories
    res1 = validate_git_url("https://github.com/Parthdarji13/DevMind-AI", resolve_dns=False)
    assert res1.is_valid is True
    assert res1.repo_name == "DevMind-AI"
    assert res1.normalized_url == "https://github.com/Parthdarji13/DevMind-AI.git"

    res2 = validate_git_url("https://gitlab.com/gitlab-org/gitlab.git", resolve_dns=False)
    assert res2.is_valid is True
    assert res2.repo_name == "gitlab"
    assert res2.normalized_url == "https://gitlab.com/gitlab-org/gitlab.git"


def test_invalid_protocols_rejected():
    invalid_protocols = [
        "http://github.com/owner/repo",
        "git://github.com/owner/repo.git",
        "ssh://git@github.com/owner/repo.git",
        "file:///etc/passwd",
        "ftp://github.com/owner/repo",
        "C:\\Projects\\repo",
        "/var/repos/project",
    ]
    for url in invalid_protocols:
        with pytest.raises(InvalidGitProtocolError):
            validate_git_url(url, resolve_dns=False)


def test_embedded_credentials_rejected():
    credential_urls = [
        "https://user:password@github.com/owner/repo.git",
        "https://token@github.com/owner/repo",
        "https://ghp_abcdef123456@github.com/owner/repo.git",
    ]
    for url in credential_urls:
        with pytest.raises(EmbeddedCredentialsError):
            validate_git_url(url, resolve_dns=False)


def test_ssrf_and_private_targets_blocked():
    ssrf_targets = [
        "https://localhost/owner/repo",
        "https://127.0.0.1/owner/repo",
        "https://0.0.0.0/owner/repo",
        "https://192.168.1.100/owner/repo",
        "https://10.0.0.5/owner/repo",
        "https://172.16.0.1/owner/repo",
        "https://169.254.169.254/latest/meta-data",
        "https://metadata.google.internal/computeMetadata/v1",
    ]
    for url in ssrf_targets:
        with pytest.raises(SSRFBlockedError):
            validate_git_url(url, resolve_dns=False)


def test_malformed_urls_rejected():
    malformed = [
        "",
        "   ",
        "https://",
        "https://github.com",
        "https://github.com/",
        "https://github.com/singlepart",
    ]
    for url in malformed:
        with pytest.raises(MalformedGitUrlError):
            validate_git_url(url, resolve_dns=False)
