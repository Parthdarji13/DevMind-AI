"""
Repository scanner and file filter pipeline.
Implements Step 8 of Antigravity guide and FR-03/FR-10 of PRD v1.2.
Scans extracted repository directory, enforces filtering rules, classifies skips,
and tracks language breakdowns without exposing secret contents.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from ...core.limits import IngestionLimits, DEFAULT_LIMITS
from .rules import (
    FilterDecision,
    FilterReason,
    should_filter_file,
)


# Extension to language display name mapping
EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".c": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".swift": "Swift",
    ".scala": "Scala",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".sql": "SQL",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".proto": "Protocol Buffers",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".txt": "Text",
}


@dataclass
class SkippedFileInfo:
    path: str
    category: str
    reason: str
    is_secret: bool = False


@dataclass
class FilteringReport:
    total_discovered: int = 0
    total_included: int = 0
    total_skipped: int = 0
    included_files: list[str] = field(default_factory=list)
    skipped_files: list[SkippedFileInfo] = field(default_factory=list)
    skipped_breakdown: dict[str, int] = field(default_factory=lambda: {
        "dependency": 0,
        "build_artifact": 0,
        "cache_runtime": 0,
        "binary_media": 0,
        "minified_lockfile": 0,
        "secret": 0,
        "oversized": 0,
        "unsupported": 0,
    })
    language_breakdown: dict[str, int] = field(default_factory=dict)
    total_included_bytes: int = 0


def detect_language(relative_path: str) -> str:
    """Returns detected language name or 'Other'."""
    p = Path(relative_path)
    ext = p.suffix.lower()
    name = p.name.lower()
    if name == "dockerfile":
        return "Dockerfile"
    if name == "makefile":
        return "Makefile"
    return EXTENSION_LANGUAGE_MAP.get(ext, "Other")


def scan_and_filter_repository(
    repo_dir: Path,
    limits: IngestionLimits = DEFAULT_LIMITS,
) -> FilteringReport:
    """
    Safely iterates through an extracted repository directory.
    Categorizes files into included vs skipped with clear reasons.
    Strictly forbids opening or reading secret files.
    """
    base_dir = repo_dir.resolve()
    report = FilteringReport()

    if not base_dir.exists() or not base_dir.is_dir():
        return report

    for path in base_dir.rglob("*"):
        if not path.is_file():
            continue

        report.total_discovered += 1

        try:
            rel_path = path.relative_to(base_dir).as_posix()
        except ValueError:
            rel_path = path.name

        try:
            file_size = path.stat().st_size
        except OSError:
            file_size = 0

        decision = should_filter_file(rel_path, file_size_bytes=file_size, limits=limits)

        if decision.is_included:
            report.total_included += 1
            report.total_included_bytes += file_size
            report.included_files.append(rel_path)

            lang = detect_language(rel_path)
            report.language_breakdown[lang] = report.language_breakdown.get(lang, 0) + 1
        else:
            report.total_skipped += 1
            cat_key = _map_reason_to_breakdown_key(decision.reason)
            report.skipped_breakdown[cat_key] = report.skipped_breakdown.get(cat_key, 0) + 1

            report.skipped_files.append(
                SkippedFileInfo(
                    path=rel_path,
                    category=cat_key,
                    reason=decision.detail,
                    is_secret=decision.is_secret,
                )
            )

    return report


def _map_reason_to_breakdown_key(reason: FilterReason) -> str:
    mapping = {
        FilterReason.DEPENDENCY: "dependency",
        FilterReason.BUILD_ARTIFACT: "build_artifact",
        FilterReason.CACHE: "cache_runtime",
        FilterReason.BINARY: "binary_media",
        FilterReason.MINIFIED: "minified_lockfile",
        FilterReason.SECRET: "secret",
        FilterReason.OVERSIZED: "oversized",
        FilterReason.UNSUPPORTED: "unsupported",
    }
    return mapping.get(reason, "unsupported")
