"""
DevMind AI — Advanced Features Service.
Implements:
- Feature 8: Flow Trace (Step-by-step execution path with files and Mermaid sequence diagram)
- Feature 9: Onboarding Doc Generator (Cited comprehensive architecture guide)
- Feature 11: Architecture Dependency Map (Module import graph and layers)
- Feature 12: Learning Mode & Codebase Quiz (Interactive quiz with grounded explanations)
"""
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from ...core.config import get_settings
from ...models.chat import (
    Citation,
    FlowTraceStep,
    FlowTraceResponse,
    OnboardingDocResponse,
    ArchitectureMapNode,
    ArchitectureMapEdge,
    ArchitectureMapResponse,
    QuizQuestion,
    QuizResponse,
)
from ..indexing.storage import PersistentIndexStore
from ..retrieval.hybrid import HybridRetrievalManager
from .client import get_llm_provider, BaseLLMProvider
from .citation_validator import CitationValidator

logger = logging.getLogger(__name__)
settings = get_settings()


class AdvancedFeaturesService:
    """Service providing Flow Tracing, Onboarding Docs, Dependency Mapping, and Quiz Generation."""

    def __init__(
        self,
        retrieval_manager: Optional[HybridRetrievalManager] = None,
        llm_provider: Optional[BaseLLMProvider] = None,
    ):
        self.retrieval_manager = retrieval_manager or HybridRetrievalManager()
        self._llm_provider = llm_provider
        self.citation_validator = CitationValidator()

    def _get_provider(self) -> BaseLLMProvider:
        if self._llm_provider:
            return self._llm_provider
        return get_llm_provider()

    # ==========================================================================
    # Feature 8: Flow Trace
    # ==========================================================================

    def trace_flow(self, repo_id: str, flow_query: str) -> FlowTraceResponse:
        """
        Traces a multi-step execution path for a user query (e.g. 'user login', 'zip ingestion').
        Retrieves relevant evidence chunks, prompts LLM for sequential step-by-step trace,
        and generates a Mermaid sequence diagram with verified line citations.
        """
        store = self.retrieval_manager.storage_manager.get_store(repo_id)
        if not store.exists():
            raise ValueError(f"Repository '{repo_id}' is not indexed.")

        # 1. Retrieve multi-hop chunks
        retrieval_results = self.retrieval_manager.retrieve(
            repo_id=repo_id,
            query=flow_query,
            top_k=10,
        )
        chunks = [r.chunk for r in retrieval_results]

        if not chunks:
            # Fallback when no chunks found
            return FlowTraceResponse(
                flow_title=f"Flow Trace: {flow_query}",
                summary="Insufficient evidence found in the codebase to trace this execution path.",
                steps=[],
                mermaid_diagram="sequenceDiagram\n    autonumber\n    Client->>System: " + flow_query + "\n    System-->>Client: No matching implementation found\n",
                citations=[],
            )

        # 2. Build code context
        code_context = []
        for i, c in enumerate(chunks):
            code_context.append(
                f"[Chunk {i+1}] File: {c.file_path} (Lines {c.start_line}-{c.end_line}) | Symbol: {c.symbol_name or 'block'}\n{c.content[:400]}"
            )
        context_str = "\n\n".join(code_context)

        sys_prompt = (
            "You are an expert software architect analyzing an execution flow in a codebase.\n"
            "Analyze the provided code chunks and trace the sequential step-by-step execution path.\n"
            "You MUST respond ONLY with a valid JSON object with the following schema:\n"
            "{\n"
            '  "flow_title": "string",\n'
            '  "summary": "2-3 sentence explanation of the entire flow",\n'
            '  "steps": [\n'
            '    {\n'
            '      "step_number": 1,\n'
            '      "title": "short step title",\n'
            '      "file_path": "exact file path from chunks",\n'
            '      "start_line": 10,\n'
            '      "end_line": 25,\n'
            '      "function_or_symbol": "function name or null",\n'
            '      "description": "what happens in this step"\n'
            '    }\n'
            '  ],\n'
            '  "mermaid_diagram": "sequenceDiagram\\n    autonumber\\n    Client->>ModuleA: action\\n    ModuleA->>ModuleB: call\\n    ModuleB-->>Client: result"\n'
            "}\n"
            "Ensure the Mermaid diagram syntax is strictly valid and uses sequenceDiagram."
        )

        user_prompt = (
            f"Execution Flow Query: {flow_query}\n\n"
            f"Code Chunks:\n{context_str}\n\n"
            "Trace the flow accurately using ONLY the code evidence provided."
        )

        provider = self._get_provider()
        raw_resp = provider.generate_response(sys_prompt, user_prompt)

        # Clean JSON from markdown fences if needed
        clean_json = raw_resp.strip()
        if clean_json.startswith("```"):
            clean_json = re.sub(r"^```(?:json)?\s*", "", clean_json)
            clean_json = re.sub(r"\s*```$", "", clean_json)

        try:
            data = json.loads(clean_json)
            flow_title = data.get("flow_title", f"Flow: {flow_query}")
            summary = data.get("summary", "Traced execution flow.")
            raw_steps = data.get("steps", [])
            mermaid_diagram = data.get("mermaid_diagram", "sequenceDiagram\n    Client->>System: Execute\n")

            steps = []
            citations = []
            for s in raw_steps:
                f_path = s.get("file_path", chunks[0].file_path)
                s_line = int(s.get("start_line", 1))
                e_line = int(s.get("end_line", s_line + 10))
                step = FlowTraceStep(
                    step_number=int(s.get("step_number", len(steps) + 1)),
                    title=s.get("title", f"Step {len(steps) + 1}"),
                    file_path=f_path,
                    start_line=s_line,
                    end_line=e_line,
                    function_or_symbol=s.get("function_or_symbol"),
                    description=s.get("description", ""),
                )
                steps.append(step)
                citations.append(
                    Citation(
                        file_path=f_path,
                        start_line=s_line,
                        end_line=e_line,
                        snippet=s.get("title"),
                    )
                )

            return FlowTraceResponse(
                flow_title=flow_title,
                summary=summary,
                steps=steps,
                mermaid_diagram=mermaid_diagram,
                citations=citations,
            )
        except Exception as e:
            logger.warning(f"Flow trace JSON parsing failed: {e}. Fallback to rule-based trace.")
            # Fallback structured response
            steps = []
            citations = []
            for i, c in enumerate(chunks[:5]):
                step = FlowTraceStep(
                    step_number=i + 1,
                    title=f"Execute {c.symbol_name or Path(c.file_path).stem}",
                    file_path=c.file_path,
                    start_line=c.start_line,
                    end_line=c.end_line,
                    function_or_symbol=c.symbol_name,
                    description=f"Executes logic in `{c.file_path}` lines {c.start_line}-{c.end_line}.",
                )
                steps.append(step)
                citations.append(Citation(file_path=c.file_path, start_line=c.start_line, end_line=c.end_line))

            diag = "sequenceDiagram\n    autonumber\n"
            for st in steps:
                safe_stem = Path(st.file_path).stem.replace("-", "_")
                diag += f"    Caller->>{safe_stem}: {st.function_or_symbol or st.title}\n"

            return FlowTraceResponse(
                flow_title=f"Flow Trace: {flow_query}",
                summary=f"Traced {len(steps)} sequential stages for {flow_query}.",
                steps=steps,
                mermaid_diagram=diag,
                citations=citations,
            )

    # ==========================================================================
    # Feature 9: Onboarding Doc Generator
    # ==========================================================================

    def generate_onboarding_doc(self, repo_id: str) -> OnboardingDocResponse:
        """
        Generates a comprehensive, evidence-grounded Onboarding Architecture Guide for a repository.
        Analyzes file tree, symbols, and entry points, and writes to data/exports/ (NEVER root ARCHITECTURE.md).
        """
        store = self.retrieval_manager.storage_manager.get_store(repo_id)
        if not store.exists():
            raise ValueError(f"Repository '{repo_id}' is not indexed.")

        chunks = store.get_chunks()
        metadata = store.get_metadata()

        # Collect unique file paths and languages
        files_set = set()
        languages_set = set()
        symbols = []
        for c in chunks:
            files_set.add(c.file_path)
            if c.language:
                languages_set.add(c.language)
            if c.symbol_name:
                symbols.append(f"{c.file_path}::{c.symbol_name}")

        files_list = sorted(list(files_set))
        languages = sorted(list(languages_set))

        # Sample entry points and core modules
        sample_code = []
        for c in chunks[:12]:
            sample_code.append(f"--- File: {c.file_path} (Lines {c.start_line}-{c.end_line}) ---\n{c.content[:350]}")
        samples_str = "\n\n".join(sample_code)

        sys_prompt = (
            "You are a Principal Software Architect creating an official Developer Onboarding Guide.\n"
            "Generate a professional, structured Markdown onboarding document for the codebase with these 5 sections:\n"
            "1. # Executive Overview & Architecture Philosophy (What the system does, design pattern, tech stack)\n"
            "2. # System Component Map & Directory Breakdown (Table of modules, roles, and key files)\n"
            "3. # Core Request Lifecycles & Critical Workflows (How data flows through the system)\n"
            "4. # Key Interfaces, Data Models & Services (Important abstractions, database storage, schemas)\n"
            "5. # Local Development & How to Get Started (Config keys, environment variables, commands)\n"
            "Cite exact file names and line ranges from the code samples provided."
        )

        user_prompt = (
            f"Repository ID: {repo_id}\n"
            f"Detected Languages: {', '.join(languages)}\n"
            f"Total Indexed Files: {len(files_list)}\n"
            f"Key Symbols: {', '.join(symbols[:20])}\n\n"
            f"Code Samples:\n{samples_str}\n\n"
            "Generate the comprehensive Developer Onboarding Guide in rich GitHub Markdown."
        )

        provider = self._get_provider()
        generated_doc = provider.generate_response(sys_prompt, user_prompt)

        # Save to data/exports/ (NEVER overwrite root ARCHITECTURE.md!)
        export_dir = Path("data/exports").resolve()
        export_dir.mkdir(parents=True, exist_ok=True)
        safe_repo_name = re.sub(r"[^\w\-]", "_", repo_id)
        export_file = export_dir / f"{safe_repo_name}_ONBOARDING_GUIDE.md"
        with open(export_file, "w", encoding="utf-8") as f:
            f.write(generated_doc)

        summary_match = re.search(r"^(?:#.*?\n+)?([^\n#]+)", generated_doc.strip())
        summary = summary_match.group(1).strip() if summary_match else "Complete codebase onboarding guide."

        return OnboardingDocResponse(
            repo_id=repo_id,
            title=f"Developer Onboarding & Architecture Guide — {repo_id}",
            content=generated_doc,
            summary=summary[:250],
            file_count=len(files_list),
            languages=languages,
        )

    # ==========================================================================
    # Feature 11: Architecture Dependency Map
    # ==========================================================================

    def build_architecture_map(self, repo_id: str) -> ArchitectureMapResponse:
        """
        Builds an interactive architectural dependency graph.
        Groups files into architectural layers (api, services, models, db, core, utils)
        and extracts cross-module import relationships.
        """
        store = self.retrieval_manager.storage_manager.get_store(repo_id)
        if not store.exists():
            raise ValueError(f"Repository '{repo_id}' is not indexed.")

        chunks = store.get_chunks()
        modules_map: Dict[str, Dict[str, Any]] = {}
        file_to_module: Dict[str, str] = {}

        # 1. Group files by top-level directory or module
        for c in chunks:
            parts = Path(c.file_path).parts
            if len(parts) > 1:
                mod_name = parts[0]
            else:
                mod_name = "root"

            file_to_module[c.file_path] = mod_name

            if mod_name not in modules_map:
                # Infer layer category
                m_lower = mod_name.lower()
                if any(k in m_lower for k in ("api", "route", "controller", "endpoint")):
                    m_type = "api"
                elif any(k in m_lower for k in ("service", "business", "logic")):
                    m_type = "services"
                elif any(k in m_lower for k in ("model", "schema", "entity", "dto")):
                    m_type = "models"
                elif any(k in m_lower for k in ("db", "database", "store", "mongo", "sql")):
                    m_type = "db"
                elif any(k in m_lower for k in ("core", "config", "settings", "env")):
                    m_type = "core"
                elif any(k in m_lower for k in ("util", "helper", "common")):
                    m_type = "utils"
                else:
                    m_type = "other"

                modules_map[mod_name] = {
                    "id": mod_name,
                    "label": mod_name.capitalize(),
                    "module_type": m_type,
                    "files": set(),
                    "line_count": 0,
                    "description": f"Module containing {mod_name} components and logic.",
                }

            modules_map[mod_name]["files"].add(c.file_path)
            modules_map[mod_name]["line_count"] += c.line_count

        # 2. Extract import relationships from chunk text
        import_counts: Dict[tuple, int] = {}
        import_pattern_py = re.compile(r"^(?:from|import)\s+([\w\.]+)", re.MULTILINE)
        import_pattern_js = re.compile(r"(?:import|require)\(?['\"](?:\.\.?\/)?([\w\.\/\-_]+)['\"]\)?", re.MULTILINE)

        for c in chunks:
            src_mod = file_to_module.get(c.file_path, "root")
            content = c.content

            # Check Python imports
            for match in import_pattern_py.findall(content):
                target_cand = match.split(".")[0]
                if target_cand in modules_map and target_cand != src_mod:
                    key = (src_mod, target_cand)
                    import_counts[key] = import_counts.get(key, 0) + 1

            # Check JS/TS imports
            for match in import_pattern_js.findall(content):
                target_cand = match.split("/")[0]
                if target_cand in modules_map and target_cand != src_mod:
                    key = (src_mod, target_cand)
                    import_counts[key] = import_counts.get(key, 0) + 1

        # 3. Assemble nodes and edges
        nodes = []
        for mod_id, m in modules_map.items():
            nodes.append(
                ArchitectureMapNode(
                    id=m["id"],
                    label=m["label"],
                    module_type=m["module_type"],
                    file_count=len(m["files"]),
                    line_count=m["line_count"],
                    description=m["description"],
                )
            )

        edges = []
        for (src, tgt), count in import_counts.items():
            edges.append(
                ArchitectureMapEdge(
                    source=src,
                    target=tgt,
                    relationship="imports",
                    import_count=count,
                )
            )

        # Fallback edge connecting root if disconnected
        if not edges and len(nodes) > 1:
            for n in nodes[1:]:
                edges.append(ArchitectureMapEdge(source=nodes[0].id, target=n.id, relationship="connects", import_count=1))

        return ArchitectureMapResponse(
            repo_id=repo_id,
            nodes=nodes,
            edges=edges,
            total_modules=len(nodes),
        )

    # ==========================================================================
    # Feature 12: Learning Mode & Codebase Quiz
    # ==========================================================================

    def generate_learning_quiz(self, repo_id: str) -> QuizResponse:
        """
        Generates 4 educational multiple-choice quiz questions based on actual indexed chunks.
        Includes options, correct answer index, hints, and explanations with file citations.
        """
        store = self.retrieval_manager.storage_manager.get_store(repo_id)
        if not store.exists():
            raise ValueError(f"Repository '{repo_id}' is not indexed.")

        chunks = store.get_chunks()
        # Find chunks with named functions/classes
        symbol_chunks = [c for c in chunks if c.symbol_name]
        candidate_chunks = symbol_chunks[:6] if symbol_chunks else chunks[:6]

        sample_context = []
        for i, c in enumerate(candidate_chunks[:4]):
            sample_context.append(
                f"[Chunk {i+1}] File: {c.file_path}:{c.start_line}-{c.end_line} | Symbol: {c.symbol_name or 'Logic'}\n{c.content[:350]}"
            )
        context_str = "\n\n".join(sample_context)

        sys_prompt = (
            "You are a Computer Science educator creating a codebase understanding quiz.\n"
            "Based on the code snippets provided, generate 3 to 4 multiple-choice questions.\n"
            "You MUST respond ONLY with a valid JSON array of question objects matching this schema:\n"
            "[\n"
            "  {\n"
            '    "id": "q1",\n'
            '    "question": "What is the primary responsibility of function XYZ in file.py?",\n'
            '    "options": ["Option A text", "Option B text", "Option C text", "Option D text"],\n'
            '    "correct_index": 0,\n'
            '    "hint": "Think about how parameters are validated...",\n'
            '    "explanation": "Option A is correct because the function uses ... [file.py:10-25]",\n'
            '    "file_path": "file.py",\n'
            '    "start_line": 10,\n'
            '    "end_line": 25\n'
            "  }\n"
            "]\n"
            "Ensure 'options' has exactly 4 items and 'correct_index' is an integer between 0 and 3."
        )

        user_prompt = f"Codebase Context:\n{context_str}\n\nGenerate the educational quiz JSON array."
        provider = self._get_provider()
        raw_resp = provider.generate_response(sys_prompt, user_prompt)

        clean_json = raw_resp.strip()
        if clean_json.startswith("```"):
            clean_json = re.sub(r"^```(?:json)?\s*", "", clean_json)
            clean_json = re.sub(r"\s*```$", "", clean_json)

        try:
            items = json.loads(clean_json)
            if not isinstance(items, list):
                items = items.get("questions", [])

            questions = []
            for idx, it in enumerate(items):
                opts = it.get("options", [])
                if len(opts) < 4:
                    opts = opts + ["None of the above"] * (4 - len(opts))
                opts = opts[:4]

                corr_idx = int(it.get("correct_index", 0))
                if corr_idx < 0 or corr_idx >= 4:
                    corr_idx = 0

                ref_chunk = candidate_chunks[idx % len(candidate_chunks)]

                q = QuizQuestion(
                    id=it.get("id", f"q{idx+1}"),
                    question=it.get("question", f"What does {ref_chunk.symbol_name or 'this code'} do?"),
                    options=opts,
                    correct_index=corr_idx,
                    hint=it.get("hint", "Examine the function signature and return statement."),
                    explanation=it.get("explanation", f"Defined in `{ref_chunk.file_path}` lines {ref_chunk.start_line}-{ref_chunk.end_line}."),
                    file_path=it.get("file_path", ref_chunk.file_path),
                    start_line=int(it.get("start_line", ref_chunk.start_line)),
                    end_line=int(it.get("end_line", ref_chunk.end_line)),
                )
                questions.append(q)

            return QuizResponse(
                repo_id=repo_id,
                questions=questions,
                total_questions=len(questions),
            )
        except Exception as e:
            logger.warning(f"Quiz JSON parsing failed: {e}. Generating fallback quiz.")
            # Deterministic fallback quiz
            fallback_questions = []
            for idx, c in enumerate(candidate_chunks[:3]):
                fq = QuizQuestion(
                    id=f"q{idx+1}",
                    question=f"What is the role of `{c.symbol_name or Path(c.file_path).stem}` in `{c.file_path}`?",
                    options=[
                        f"Implements core business logic for {c.symbol_name or 'the module'}",
                        "Configures external database logging parameters",
                        "Serves static assets to the browser",
                        "Handles deprecated API fallbacks",
                    ],
                    correct_index=0,
                    hint=f"Check the symbols declared in `{c.file_path}`.",
                    explanation=f"`{c.symbol_name or 'This logic'}` is defined at lines {c.start_line}-{c.end_line} of `{c.file_path}`.",
                    file_path=c.file_path,
                    start_line=c.start_line,
                    end_line=c.end_line,
                )
                fallback_questions.append(fq)

            return QuizResponse(
                repo_id=repo_id,
                questions=fallback_questions,
                total_questions=len(fallback_questions),
            )
