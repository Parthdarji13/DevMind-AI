"""
Tests for repository limits and file filtering rules.
Verifies FR-03, Step 6, and security secret exclusion.
"""
import sys
from pathlib import Path
import pytest

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.filtering.rules import (
    FilterReason,
    should_filter_file,
    is_secret_file,
    is_supported_source_file,
)
from app.core.limits import IngestionLimits


def test_supported_source_files_included():
    valid_files = [
        "src/main.py",
        "frontend/src/App.tsx",
        "frontend/src/index.ts",
        "pkg/server/handler.go",
        "src/lib.rs",
        "scripts/deploy.sh",
        "README.md",
        "Dockerfile",
        "Makefile",
        "config.yaml",
        "schema.sql",
    ]
    for path in valid_files:
        decision = should_filter_file(path, file_size_bytes=1000)
        assert decision.is_included is True, f"Expected {path} to be included"
        assert decision.reason == FilterReason.INCLUDED


def test_dependency_directories_excluded():
    dep_files = [
        "node_modules/lodash/index.js",
        "src/node_modules/pkg/main.js",
        "vendor/bundle/gem/lib.rb",
        "packages/external/lib.js",
    ]
    for path in dep_files:
        decision = should_filter_file(path)
        assert decision.is_included is False
        assert decision.reason == FilterReason.DEPENDENCY


def test_build_artifacts_excluded():
    build_files = [
        "dist/bundle.js",
        "build/static/js/main.js",
        ".next/server/pages/index.js",
        "out/index.html",
        "target/debug/app",
    ]
    for path in build_files:
        decision = should_filter_file(path)
        assert decision.is_included is False
        assert decision.reason == FilterReason.BUILD_ARTIFACT


def test_cache_and_venv_excluded():
    cache_files = [
        ".git/HEAD",
        "__pycache__/config.cpython-312.pyc",
        ".venv/lib/site-packages/pip.py",
        "venv/bin/activate",
        ".pytest_cache/v/cache/lastfailed",
        ".idea/workspace.xml",
    ]
    for path in cache_files:
        decision = should_filter_file(path)
        assert decision.is_included is False
        assert decision.reason == FilterReason.CACHE


def test_binary_and_media_excluded():
    binaries = [
        "assets/logo.png",
        "images/photo.jpeg",
        "fonts/inter.woff2",
        "docs/spec.pdf",
        "tools/app.exe",
        "archive.zip",
        "data/db.sqlite3",
    ]
    for path in binaries:
        decision = should_filter_file(path)
        assert decision.is_included is False
        assert decision.reason == FilterReason.BINARY


def test_minified_and_lockfiles_excluded():
    minified = [
        "public/bundle.min.js",
        "style.min.css",
        "app.js.map",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Cargo.lock",
    ]
    for path in minified:
        decision = should_filter_file(path)
        assert decision.is_included is False
        assert decision.reason == FilterReason.MINIFIED


def test_secret_files_excluded_with_flag():
    secrets = [
        ".env",
        ".env.local",
        ".env.production",
        "config/.env.test",
        "certs/server.pem",
        "keys/private.key",
        "ssh/id_rsa",
        "ssh/id_ed25519",
        "auth/credentials.json",
        "secrets/service-account.json",
    ]
    for path in secrets:
        decision = should_filter_file(path)
        assert decision.is_included is False, f"Expected {path} to be excluded"
        assert decision.is_secret is True, f"Expected {path} to have is_secret=True"
        assert decision.reason == FilterReason.SECRET


def test_oversized_files_excluded():
    limits = IngestionLimits(max_file_kb=500)
    # 400 KB is within limit
    ok_decision = should_filter_file("src/big.py", file_size_bytes=400 * 1024, limits=limits)
    assert ok_decision.is_included is True

    # 600 KB exceeds limit
    oversized_decision = should_filter_file("src/huge.py", file_size_bytes=600 * 1024, limits=limits)
    assert oversized_decision.is_included is False
    assert oversized_decision.reason == FilterReason.OVERSIZED


def test_windows_and_posix_path_normalization():
    win_path = "src\\components\\Header.tsx"
    decision = should_filter_file(win_path)
    assert decision.is_included is True
    assert decision.reason == FilterReason.INCLUDED

    win_secret = "config\\.env.local"
    sec_decision = should_filter_file(win_secret)
    assert sec_decision.is_included is False
    assert sec_decision.is_secret is True
