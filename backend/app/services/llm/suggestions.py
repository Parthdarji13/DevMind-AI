"""
Service for deriving repository-tailored suggested inquiries from indexed code chunks and symbols.
Ref: Step 29 of execution guide; PRD Section 6 (FR-07).
Derives questions directly from detected files, symbols, entry points, and architectures.
Explicitly clarifies that suggestions are exploratory prompts, not pre-verified claims.
"""
from pathlib import Path
from typing import Optional
import re

from ...models.chat import SuggestedQuestion, SuggestedQuestionsResponse
from ...models.chunk import CodeChunk
from ..indexing.storage import IndexStorageManager, PersistentIndexStore


class SuggestionService:
    """Extracts repository-specific suggested questions from indexed code chunks and AST symbols."""

    def __init__(self, storage_manager: Optional[IndexStorageManager] = None):
        self.storage_manager = storage_manager or IndexStorageManager()

    def generate_suggestions(self, repo_id: str) -> SuggestedQuestionsResponse:
        """
        Derives 4-6 repository-specific questions based on indexed files and symbols.
        Guarantees:
        - Every suggestion is tied to a real file path or symbol name via `derived_from`.
        - `is_verified` is strictly False so the UI does not imply questions are pre-verified answers.
        """
        store = self.storage_manager.get_store(repo_id)
        if not store.exists():
            return SuggestedQuestionsResponse(
                repo_id=repo_id,
                suggestions=[],
                total_chunks_analyzed=0,
                languages_detected=[],
            )

        chunks = store.get_chunks()
        if not chunks:
            return SuggestedQuestionsResponse(
                repo_id=repo_id,
                suggestions=[],
                total_chunks_analyzed=0,
                languages_detected=[],
            )

        meta = store.get_metadata() or {}
        detected_languages = meta.get("languages_detected", [])
        if not detected_languages:
            detected_languages = sorted(
                list(set(c.language for c in chunks if c.language and c.language != "text"))
            )

        # Collect unique file paths and prominent symbols
        file_paths = sorted(list(set(c.file_path for c in chunks)))
        symbols_with_files = [
            (c.symbol_name.strip(), c.file_path)
            for c in chunks
            if c.symbol_name
            and len(c.symbol_name.strip()) >= 3
            and not c.symbol_name.strip().startswith(("#", "//", "/*", "*", "-"))
        ]

        suggestions: list[SuggestedQuestion] = []
        added_questions: set[str] = set()

        def add_suggestion(q: str, cat: str, derived: str) -> None:
            if q not in added_questions and len(suggestions) < 6:
                added_questions.add(q)
                suggestions.append(
                    SuggestedQuestion(
                        question=q,
                        category=cat,
                        derived_from=derived,
                        is_verified=False,
                    )
                )

        # 1. Architecture & Entry Points
        entry_patterns = [
            r"main\.(py|go|rs|cpp|ts|js)",
            r"app\.(py|js|ts|tsx)",
            r"index\.(js|ts|html)",
            r"page\.(tsx|jsx|js)",
            r"server\.(js|ts|py)",
            r"README\.md",
            r"package\.json",
            r"Cargo\.toml",
        ]
        entry_candidates = [
            f for f in file_paths
            if any(re.search(pat, f, re.IGNORECASE) for pat in entry_patterns)
        ]
        if entry_candidates:
            primary_entry = entry_candidates[0]
            add_suggestion(
                f"How is the application initialized and structured in {primary_entry}?",
                "Architecture",
                primary_entry,
            )

        # 2. API & Routing
        api_patterns = [
            r"route\.(ts|js)",
            r"routes?/",
            r"api/",
            r"controllers?/",
            r"endpoints?/",
            r"views\.py",
            r"urls\.py",
        ]
        api_candidates = [
            f for f in file_paths
            if any(re.search(pat, f, re.IGNORECASE) for pat in api_patterns)
        ]
        if api_candidates:
            primary_api = api_candidates[0]
            add_suggestion(
                f"Which endpoints and request handlers are defined in {primary_api}?",
                "API & Routing",
                primary_api,
            )

        # 3. Data & Models
        model_patterns = [
            r"models?/",
            r"schemas?/",
            r"entities/",
            r"prisma",
            r"db\.",
            r"database",
            r"store\.",
        ]
        model_candidates = [
            f for f in file_paths
            if any(re.search(pat, f, re.IGNORECASE) for pat in model_patterns)
        ]
        if model_candidates:
            primary_model = model_candidates[0]
            add_suggestion(
                f"How is data structured and persisted in {primary_model}?",
                "Data & Models",
                primary_model,
            )

        # 4. Authentication & Security
        auth_patterns = [
            r"auth",
            r"login",
            r"jwt",
            r"session",
            r"permission",
            r"security",
            r"middleware",
            r"guard",
        ]
        auth_candidates = [
            f for f in file_paths
            if any(re.search(pat, f, re.IGNORECASE) for pat in auth_patterns)
        ]
        if auth_candidates:
            primary_auth = auth_candidates[0]
            add_suggestion(
                f"How are authentication and security controls implemented in {primary_auth}?",
                "Security & Auth",
                primary_auth,
            )

        # 5. Core Symbols / Components
        generic_words = {"test", "error", "helper", "index", "default", "props", "state", "type", "interface"}
        meaningful_symbols = [
            (sym, f) for (sym, f) in symbols_with_files
            if sym.lower() not in generic_words and len(sym) >= 4
        ]
        if meaningful_symbols:
            chosen_sym, sym_file = meaningful_symbols[0]
            add_suggestion(
                f"What is the responsibility and implementation of '{chosen_sym}' in {sym_file}?",
                "Core Logic",
                f"{sym_file} ({chosen_sym})",
            )

        # 6. Second Distinct Symbol (if available)
        if len(meaningful_symbols) > 1 and len(suggestions) < 5:
            distinct_symbols = [(s, f) for (s, f) in meaningful_symbols if f != sym_file]
            second_sym, second_file = distinct_symbols[0] if distinct_symbols else meaningful_symbols[1]
            add_suggestion(
                f"How does '{second_sym}' operate within {second_file}?",
                "Core Logic",
                f"{second_file} ({second_sym})",
            )

        # 7. Fallback to file-specific questions if fewer than 4 generated
        if len(suggestions) < 4:
            for f in file_paths:
                if len(suggestions) >= 4:
                    break
                if not any(f in s.derived_from for s in suggestions):
                    add_suggestion(
                        f"What are the main functions or configurations implemented in {f}?",
                        "Components",
                        f,
                    )

        return SuggestedQuestionsResponse(
            repo_id=repo_id,
            suggestions=suggestions,
            total_chunks_analyzed=len(chunks),
            languages_detected=detected_languages,
        )
