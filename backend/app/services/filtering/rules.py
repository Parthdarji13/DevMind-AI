"""
Filtering rules and limits enforcement for DevMind AI.
Implements FR-03, Step 6, and Section 17.4 of DevMind AI PRD.
"""
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePath
import re
from ...core.limits import IngestionLimits, DEFAULT_LIMITS


class FilterReason(str, Enum):
    INCLUDED = "included"
    DEPENDENCY = "dependency_directory"
    BUILD_ARTIFACT = "build_artifact"
    CACHE = "cache_or_runtime"
    BINARY = "binary_or_media"
    SECRET = "secret_file"
    MINIFIED = "minified_or_lockfile"
    OVERSIZED = "file_oversized"
    UNSUPPORTED = "unsupported_extension"


@dataclass(frozen=True)
class FilterDecision:
    is_included: bool
    reason: FilterReason
    detail: str
    is_secret: bool = False


# Ignored directory names (checked anywhere in the relative path)
DEPENDENCY_DIRS = {
    "node_modules",
    "vendor",
    "bower_components",
    "packages",
}

BUILD_DIRS = {
    "dist",
    "build",
    "out",
    "target",
    "bin",
    "obj",
    ".next",
    ".nuxt",
    ".output",
}

CACHE_AND_VENV_DIRS = {
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    ".yarn",
    ".venv",
    "venv",
    "env",
    "ENV",
    ".tox",
    ".nox",
    ".idea",
    ".vscode",
}

IGNORED_DIRECTORIES = DEPENDENCY_DIRS | BUILD_DIRS | CACHE_AND_VENV_DIRS

# Secret file signatures
SECRET_FILENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.test",
    ".env.staging",
    "id_rsa",
    "id_dsa",
    "id_ed25519",
    "id_ecdsa",
    "credentials.json",
    "service-account.json",
    "service_account.json",
}

SECRET_EXTENSIONS = {
    ".pem",
    ".key",
    ".pfx",
    ".p12",
    ".pkcs12",
    ".kdbx",
    ".keystore",
    ".jks",
}

# Binary and media extensions
BINARY_EXTENSIONS = {
    # Images & Media
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff",
    ".mp3", ".wav", ".ogg", ".mp4", ".mov", ".avi", ".mkv", ".webm",
    # Archives
    ".zip", ".tar", ".gz", ".tgz", ".7z", ".rar", ".bz2", ".xz",
    # Binaries & Compiled
    ".exe", ".dll", ".so", ".dylib", ".class", ".pyc", ".pyo", ".wasm", ".o", ".a",
    # Fonts
    ".ttf", ".woff", ".woff2", ".eot", ".otf",
    # Office & Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # Database files
    ".sqlite", ".sqlite3", ".db", ".parquet",
}

# Minified and lockfile patterns
LOCKFILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "cargo.lock",
    "poetry.lock",
    "composer.lock",
    "gemfile.lock",
}

# Supported source and text extensions
SUPPORTED_EXTENSIONS = {
    # Web & Scripts
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".html", ".htm", ".css", ".scss", ".sass", ".less", ".vue", ".svelte",
    # Backend & Systems
    ".py", ".pyi",
    ".go",
    ".rs",
    ".java",
    ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx",
    ".cs",
    ".rb",
    ".php",
    ".kt", ".kts",
    ".swift",
    ".scala",
    # Data & Config
    ".json",
    ".yaml", ".yml",
    ".toml",
    ".xml",
    ".sql",
    ".graphql", ".gql",
    ".proto",
    # Shell & Documentation
    ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
    ".md", ".markdown", ".txt", ".rst",
}

SPECIAL_TEXT_FILENAMES = {
    "dockerfile",
    "makefile",
    "procfile",
    "jenkinsfile",
    "readme",
    "license",
}


def is_secret_file(path_str: str) -> bool:
    """Detects likely secrets based on filename, extension, or patterns."""
    p = PurePath(path_str.replace("\\", "/"))
    filename_lower = p.name.lower()

    if filename_lower in SECRET_FILENAMES:
        return True

    if filename_lower.startswith(".env."):
        return True

    if p.suffix.lower() in SECRET_EXTENSIONS:
        return True

    # Pattern check for private keys or credential files
    if re.search(r"(private_key|client_secret|api_key|secret_key)", filename_lower):
        return True

    return False


def is_supported_source_file(path_str: str) -> bool:
    """Checks if a file extension or name matches supported source code formats."""
    p = PurePath(path_str.replace("\\", "/"))
    ext = p.suffix.lower()
    filename_lower = p.name.lower()

    if ext in SUPPORTED_EXTENSIONS:
        return True

    if filename_lower in SPECIAL_TEXT_FILENAMES:
        return True

    return False


def should_filter_file(
    relative_path: str,
    file_size_bytes: int = 0,
    limits: IngestionLimits = DEFAULT_LIMITS,
) -> FilterDecision:
    """
    Evaluates whether a relative repository file path should be included or skipped.
    Never exposes secret contents.
    """
    normalized = relative_path.replace("\\", "/").strip("/")
    parts = normalized.split("/")
    filename = parts[-1] if parts else ""
    filename_lower = filename.lower()
    p = PurePath(normalized)
    ext = p.suffix.lower()

    # 1. Secret detection (Priority rule)
    if is_secret_file(normalized):
        return FilterDecision(
            is_included=False,
            reason=FilterReason.SECRET,
            detail="Excluded likely secret or credential file",
            is_secret=True,
        )

    # 2. Directory checks
    for part in parts[:-1]:
        part_lower = part.lower()
        if part_lower in DEPENDENCY_DIRS:
            return FilterDecision(
                is_included=False,
                reason=FilterReason.DEPENDENCY,
                detail=f"In dependency folder '{part}'",
            )
        if part_lower in BUILD_DIRS:
            return FilterDecision(
                is_included=False,
                reason=FilterReason.BUILD_ARTIFACT,
                detail=f"In build/distribution folder '{part}'",
            )
        if part_lower in CACHE_AND_VENV_DIRS:
            return FilterDecision(
                is_included=False,
                reason=FilterReason.CACHE,
                detail=f"In cache, venv, or IDE folder '{part}'",
            )

    # 3. Binary and media checks
    if ext in BINARY_EXTENSIONS:
        return FilterDecision(
            is_included=False,
            reason=FilterReason.BINARY,
            detail=f"Binary or media format ({ext})",
        )

    # 4. Minified and lockfile checks
    if filename_lower.endswith(".min.js") or filename_lower.endswith(".min.css") or filename_lower.endswith(".map"):
        return FilterDecision(
            is_included=False,
            reason=FilterReason.MINIFIED,
            detail="Minified code or sourcemap",
        )

    if filename_lower in LOCKFILES:
        return FilterDecision(
            is_included=False,
            reason=FilterReason.MINIFIED,
            detail="Package lockfile excluded to prevent noise",
        )

    # 5. File size checks
    if file_size_bytes > 0 and not limits.validate_file_size(file_size_bytes):
        return FilterDecision(
            is_included=False,
            reason=FilterReason.OVERSIZED,
            detail=f"File size ({file_size_bytes} bytes) exceeds limit ({limits.max_file_kb} KB)",
        )

    # 6. Supported source check
    if is_supported_source_file(normalized):
        return FilterDecision(
            is_included=True,
            reason=FilterReason.INCLUDED,
            detail="Supported source code or text file",
        )

    return FilterDecision(
        is_included=False,
        reason=FilterReason.UNSUPPORTED,
        detail=f"Unsupported file format ({ext or 'no extension'})",
    )
