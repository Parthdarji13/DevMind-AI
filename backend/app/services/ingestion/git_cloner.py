"""
Controlled public Git repository fetch and shallow cloning.
Ref: PRD Section 6 (FR-02), Section 10; Step 11 of execution guide.
Enforces timeouts, shallow depth, disables interactive prompts, and cleans up .git artifacts.
"""
from pathlib import Path
import os
import shutil
import subprocess
from typing import Optional

from ...core.limits import IngestionLimits, DEFAULT_LIMITS
from .git_validator import (
    validate_git_url,
    GitValidationResult,
    GitValidationError,
)
from ..filtering.scanner import scan_and_filter_repository, FilteringReport


class GitCloneError(Exception):
    """Raised when git clone fails."""
    pass


class GitTimeoutError(GitCloneError):
    """Raised when git clone exceeds the configured timeout."""
    pass


def clone_and_filter_public_repo(
    raw_url: str,
    target_dir: Path,
    limits: IngestionLimits = DEFAULT_LIMITS,
    resolve_dns: bool = True,
) -> tuple[GitValidationResult, FilteringReport]:
    """
    Validates URL, shallow clones the repository with strict timeouts,
    removes the .git folder, and runs the filtering engine.
    """
    # 1. Validate URL and SSRF protections
    validation = validate_git_url(raw_url, resolve_dns=resolve_dns)

    target_path = Path(target_dir).resolve()
    target_path.mkdir(parents=True, exist_ok=True)

    # 2. Build non-interactive git environment
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "echo"

    # Shallow clone with depth 1, single branch
    cmd = [
        "git",
        "clone",
        "--depth", "1",
        "--single-branch",
        "--no-tags",
        validation.normalized_url,
        str(target_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=limits.git_clone_timeout_seconds,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        shutil.rmtree(target_path, ignore_errors=True)
        raise GitTimeoutError(
            f"Git clone timed out after {limits.git_clone_timeout_seconds} seconds."
        ) from e
    except Exception as e:
        shutil.rmtree(target_path, ignore_errors=True)
        raise GitCloneError(f"Unexpected error running git clone: {str(e)}") from e

    if result.returncode != 0:
        shutil.rmtree(target_path, ignore_errors=True)
        stderr_msg = result.stderr.strip()
        # Provide helpful, safe failure diagnostic
        if "Authentication failed" in stderr_msg or "could not read Username" in stderr_msg:
            detail = "Repository is private or requires authentication. DevMind AI MVP supports public repositories only."
        elif "not found" in stderr_msg.lower() or "repository not found" in stderr_msg.lower():
            detail = f"Repository not found at '{raw_url}'. Please check that the URL is correct."
        else:
            detail = f"Git clone failed: {stderr_msg or 'Unknown git error'}"
        raise GitCloneError(detail)

    # 3. Strip .git directory to remove hooks, history, and reduce disk footprint
    dot_git = target_path / ".git"
    if dot_git.exists():
        # Handle read-only files on Windows during .git deletion
        def handle_remove_readonly(func, path, exc):
            try:
                os.chmod(path, 0o777)
                func(path)
            except Exception:
                pass
        shutil.rmtree(dot_git, onerror=handle_remove_readonly)

    # 4. Scan and filter files
    filter_report = scan_and_filter_repository(target_path, limits=limits)

    if filter_report.total_discovered > limits.max_files:
        shutil.rmtree(target_path, ignore_errors=True)
        raise GitCloneError(
            f"Repository contains {filter_report.total_discovered} files, exceeding limit of {limits.max_files}."
        )

    if filter_report.total_included == 0:
        shutil.rmtree(target_path, ignore_errors=True)
        raise GitCloneError("No supported source code or text files found in the cloned repository.")

    return validation, filter_report
