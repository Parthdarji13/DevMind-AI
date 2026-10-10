"""
Unit tests for repository scanning and filtering report pipeline (Step 8).
Verifies that intended files are included, noise/secrets are categorized and excluded,
and secret contents are never exposed.
"""
import sys
import tempfile
from pathlib import Path
import pytest

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.filtering.scanner import scan_and_filter_repository, detect_language


def create_mock_repository(base_dir: Path) -> dict[str, str]:
    """Sets up a realistic mock repository structure on disk."""
    files = {
        # Source files (to be included)
        "src/main.py": "print('hello from devmind')",
        "src/utils.ts": "export const add = (a: number, b: number) => a + b;",
        "README.md": "# Sample Project",
        # Dependencies (to be skipped)
        "node_modules/axios/index.js": "module.exports = {};",
        # Build artifacts (to be skipped)
        "dist/bundle.js": "var a=1; console.log(a);",
        # Caches & venvs (to be skipped)
        ".venv/lib/python3.12/site.py": "# virtualenv site module",
        # Binaries (to be skipped)
        "assets/logo.png": "binary_content_here",
        # Secrets (to be skipped with is_secret=True)
        ".env": "SUPER_SECRET_KEY=1234567890",
        "keys/id_rsa": "BEGIN OPENSSH PRIVATE KEY",
        # Minified / lockfiles (to be skipped)
        "package-lock.json": '{"name": "mock", "lockfileVersion": 3}',
        # Unsupported format (to be skipped)
        "data/sample.unknownext": "random data",
    }

    for rel_path, content in files.items():
        full_path = base_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    return files


def test_scan_and_filter_repository():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir)
        create_mock_repository(repo_dir)

        report = scan_and_filter_repository(repo_dir)

        # 1. Total counts
        assert report.total_discovered == 11
        assert report.total_included == 3
        assert report.total_skipped == 8

        # 2. Included files check
        assert set(report.included_files) == {"src/main.py", "src/utils.ts", "README.md"}

        # 3. Categorized skip breakdown
        assert report.skipped_breakdown["dependency"] == 1
        assert report.skipped_breakdown["build_artifact"] == 1
        assert report.skipped_breakdown["cache_runtime"] == 1
        assert report.skipped_breakdown["binary_media"] == 1
        assert report.skipped_breakdown["secret"] == 2
        assert report.skipped_breakdown["minified_lockfile"] == 1
        assert report.skipped_breakdown["unsupported"] == 1

        # 4. Secret items check: verify is_secret flag
        secret_skips = [s for s in report.skipped_files if s.is_secret]
        assert len(secret_skips) == 2
        secret_paths = {s.path for s in secret_skips}
        assert ".env" in secret_paths
        assert "keys/id_rsa" in secret_paths

        # 5. Language detection
        assert report.language_breakdown.get("Python") == 1
        assert report.language_breakdown.get("TypeScript") == 1
        assert report.language_breakdown.get("Markdown") == 1


def test_detect_language():
    assert detect_language("app/main.py") == "Python"
    assert detect_language("src/App.tsx") == "TypeScript"
    assert detect_language("server/main.go") == "Go"
    assert detect_language("Dockerfile") == "Dockerfile"
    assert detect_language("Makefile") == "Makefile"
    assert detect_language("docs/README.md") == "Markdown"
    assert detect_language("something.xyz") == "Other"
