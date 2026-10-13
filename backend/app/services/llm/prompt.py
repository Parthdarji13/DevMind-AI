"""
Evidence and prompt contract for DevMind AI codebase Q&A.
Ref: PRD Section 6 (FR-07, FR-08, FR-09), Section 7, Section 8; Step 20 of execution guide.
Enforces:
1. Sending only selected relevant chunks (never the entire repository).
2. Evidence-based answers grounded strictly in retrieved chunks.
3. Explicit abstention instruction when evidence is missing or insufficient.
4. Clear separation of direct evidence from architectural inference ([Inference]).
5. Citation syntax: [File: <path>, Lines: <start>-<end>].
"""
import re
from typing import Optional, Union

from ...models.chat import ChatMessage, Citation
from ...models.chunk import CodeChunk
from ..retrieval.bm25 import SearchResult

SYSTEM_PROMPT = """You are DevMind AI, an expert, objective, evidence-grounded codebase assistant.
Your goal is to answer developer questions accurately using ONLY the provided retrieved codebase evidence.

NON-NEGOTIABLE GROUNDING RULES:
1. STRICT EVIDENCE BASE: Answer the question using ONLY the source code chunks provided in the "RETRIEVED CODEBASE EVIDENCE" section below. Do NOT use unverified assumptions or external code knowledge not present in the evidence.
2. CITATION REQUIREMENT: Every factual claim, function description, workflow explanation, and code reference MUST be cited using the exact citation format:
   [File: <file_path>, Lines: <start_line>-<end_line>]
   Only cite files and line ranges that appear in the provided evidence. Never invent file paths or line numbers.
3. INFERENCE SEPARATION: If you must extrapolate architectural design or deduce intent that is NOT directly stated in the code, you MUST explicitly separate it using the tag `[Inference]` or by stating "Based on architectural inference: ...".
4. ABSTENTION RULE: If the provided evidence chunks do NOT contain sufficient information to answer the question, you MUST explicitly state that the evidence does not contain the answer (e.g. "The retrieved codebase evidence does not contain information about <topic>."). Never fabricate code, configurations, or features that are not in the evidence.
5. CODE INTEGRITY: Preserve exact identifier names (classes, functions, variables, constants, endpoints) and file paths exactly as they appear in the source chunks.
6. MULTILINGUAL & SCRIPT PRESERVATION (Hindi & Hinglish):
   - When the user asks in Hindi (Devanagari script) or Hinglish (Hindi written using Latin script, e.g. "kaise handle hota hai", "kaha define hai"), respond in the user's chosen language and style naturally.
   - NON-NEGOTIABLE CODE PRESERVATION: Preserve ALL file paths (e.g. `src/lib/auth.ts`), class names, function names, variable names, HTTP methods, and API routes in their exact verbatim English/code form. NEVER translate code symbols, filenames, or technical terms into Hindi or Devanagari.
   - EXACT CITATION FORMAT: Every citation MUST strictly adhere to the standard English format: `[File: <file_path>, Lines: <start>-<end>]`. Never translate citation tags or line bounds.
7. CLEAN FORMATTING & READABILITY:
   - Organize answers with clean Markdown headings (`### 1. ...`), concise bullet points, and inline code tags (`code`).
   - Keep answers well-structured and executive. Show short, focused 2-4 line code snippets only when they clarify an explanation; do not dump massive repetitive blocks.
   - Use clean bold lead-ins (e.g. `1. **Heading**: Explanation... [File: ..., Lines: ...]`) and avoid awkward double punctuation like colons after citations or dashes after colons.
"""

ABSTENTION_PHRASES = [
    "does not contain",
    "do not contain",
    "insufficient evidence",
    "not found in the retrieved evidence",
    "cannot be determined from the provided",
    "no evidence",
    "not mentioned in the codebase evidence",
    "cannot find any reference",
    "not provided in the retrieved chunks",
    # Hinglish abstention phrases
    "evidence me nahi",
    "codebase me nahi",
    "jankari nahi hai",
    "koi reference nahi",
    "paryapt evidence nahi",
    "evidence me uplabdh nahi",
    "information nahi mili",
    "information nahi hai",
    "reference nahi mila",
    # Hindi Devanagari abstention phrases
    "जानकारी उपलब्ध नहीं",
    "कोई संदर्भ नहीं",
    "पर्याप्त साक्ष्य नहीं",
    "कोडबेस में नहीं",
    "उपलब्ध नहीं है",
]


def format_chunk_context(
    chunks: list[Union[CodeChunk, SearchResult]],
    max_total_chars: Optional[int] = None,
) -> str:
    """
    Formats retrieved code chunks into a structured, delimited prompt block.
    Guarantees that only selected chunks are included.
    """
    if not chunks:
        return "No relevant code chunks were retrieved for this question."

    formatted_blocks: list[str] = []
    cumulative_chars = 0

    for idx, item in enumerate(chunks):
        chunk: CodeChunk = item.chunk if isinstance(item, SearchResult) else item
        block = (
            f"=== EVIDENCE CHUNK {idx + 1} [ID: {chunk.chunk_id}] ===\n"
            f"File: {chunk.file_path}\n"
            f"Lines: {chunk.start_line}-{chunk.end_line}\n"
            f"Language: {chunk.language}\n"
            f"Symbol: {chunk.symbol_name or 'N/A'}\n"
            f"--- Source Code ---\n"
            f"{chunk.content}\n"
            f"=== END EVIDENCE CHUNK {idx + 1} ==="
        )

        block_len = len(block)
        if max_total_chars is not None and (cumulative_chars + block_len > max_total_chars):
            if formatted_blocks:
                # Stop adding more chunks if context budget would be exceeded
                break

        formatted_blocks.append(block)
        cumulative_chars += block_len

    return "\n\n".join(formatted_blocks)


def build_qa_prompt(
    question: str,
    chunks: list[Union[CodeChunk, SearchResult]],
    history: Optional[list[ChatMessage]] = None,
    repo_name: Optional[str] = None,
    max_total_chars: Optional[int] = 12000,
) -> tuple[str, str]:
    """
    Builds the (system_prompt, user_prompt) tuple adhering to the evidence contract.
    """
    evidence_text = format_chunk_context(chunks, max_total_chars=max_total_chars)

    history_text = ""
    if history:
        history_lines: list[str] = []
        for msg in history[-6:]:  # Bound history to last 6 turns
            history_lines.append(f"{msg.role.upper()}: {msg.content}")
        history_text = (
            "--- PRIOR CONVERSATION HISTORY ---\n"
            + "\n".join(history_lines)
            + "\n-----------------------------------\n\n"
        )

    repo_banner = f"REPOSITORY CONTEXT: {repo_name}\n" if repo_name else ""

    from ..retrieval.multilingual import detect_language
    lang = detect_language(question)
    lang_directive = ""
    if lang == "hindi":
        lang_directive = (
            "\n- LANGUAGE: The developer asked in Hindi. Answer in Hindi naturally, while strictly "
            "preserving all code identifiers, filenames, paths, and citation formats in their exact original English format."
        )
    elif lang == "hinglish":
        lang_directive = (
            "\n- LANGUAGE: The developer asked in Hinglish. Answer in Hinglish naturally, while strictly "
            "preserving all code identifiers, filenames, paths, and citation formats in their exact original English format."
        )

    user_prompt = (
        f"{repo_banner}"
        f"{history_text}"
        f"--- RETRIEVED CODEBASE EVIDENCE ---\n"
        f"{evidence_text}\n"
        f"------------------------------------\n\n"
        f"DEVELOPER QUESTION:\n{question.strip()}\n\n"
        f"Please provide an accurate, evidence-grounded answer following all rules:\n"
        f"- Cite all references using [File: <path>, Lines: <start>-<end>].\n"
        f"- Separate inferences using [Inference].\n"
        f"- If the evidence is insufficient, explicitly state that the evidence does not contain the answer."
        f"{lang_directive}"
    )

    return SYSTEM_PROMPT, user_prompt


def extract_citations(text: str) -> list[Citation]:
    """
    Parses citations from model output matching:
    - [File: path/to/file.py, Lines: 10-25]
    - [File: path/to/file.py, Line: 10]
    - [path/to/file.py:10-25]
    """
    citations: list[Citation] = []
    seen: set[tuple[str, int, int]] = set()

    # Pattern 1: [File: <path>, Lines: <start>-<end>] or Line: <start>
    p1 = re.finditer(
        r"\[(?:File:\s*)?([A-Za-z0-9_\-\./\\]+),\s*Lines?:\s*(\d+)(?:-(\d+))?\]",
        text,
        re.IGNORECASE,
    )
    for m in p1:
        path = m.group(1).replace("\\", "/").strip()
        start = int(m.group(2))
        end = int(m.group(3)) if m.group(3) else start
        if (path, start, end) not in seen:
            seen.add((path, start, end))
            citations.append(Citation(file_path=path, start_line=start, end_line=end))

    # Pattern 2: [path/to/file.py:10-25]
    p2 = re.finditer(
        r"\[([A-Za-z0-9_\-\./\\]+\.[a-zA-Z0-9]+):(\d+)(?:-(\d+))?\]",
        text,
    )
    for m in p2:
        path = m.group(1).replace("\\", "/").strip()
        start = int(m.group(2))
        end = int(m.group(3)) if m.group(3) else start
        if (path, start, end) not in seen:
            seen.add((path, start, end))
            citations.append(Citation(file_path=path, start_line=start, end_line=end))

    return citations


def is_abstention(text: str, has_citations: bool = False) -> bool:
    """
    Detects whether the response abstains due to missing or insufficient evidence.
    Guards against false positives when verified citations exist or when describing code attributes.
    """
    if has_citations:
        return False

    t_lower = text.lower()
    has_phrase = any(phrase in t_lower for phrase in ABSTENTION_PHRASES)
    if not has_phrase:
        return False

    # Guard against false positives: if matching generic "does not contain", ensure it anchors to evidence context
    if "does not contain" in t_lower or "do not contain" in t_lower:
        evidence_anchors = ["evidence", "codebase", "information", "answer", "retrieved", "mention", "chunk"]
        if not any(anchor in t_lower for anchor in evidence_anchors):
            return False

    return True


def has_inference(text: str) -> bool:
    """Detects whether the response includes explicit inference callouts."""
    t_lower = text.lower()
    return "[inference]" in t_lower or "architectural inference" in t_lower


def validate_citations_against_chunks(
    citations: list[Citation],
    chunks: list[Union[CodeChunk, SearchResult]],
) -> list[Citation]:
    """
    Validates extracted citations against provided evidence chunks.
    Ensures that cited file path exists in the retrieved chunks and overlapping line ranges match.
    Attaches chunk_id and exact source snippet when valid.
    """
    valid_citations: list[Citation] = []
    chunk_list = [c.chunk if isinstance(c, SearchResult) else c for c in chunks]

    for cit in citations:
        matched_chunk: Optional[CodeChunk] = None
        for chunk in chunk_list:
            if chunk.file_path == cit.file_path:
                # Check line range overlap or proximity
                if not (cit.end_line < chunk.start_line or cit.start_line > chunk.end_line):
                    matched_chunk = chunk
                    break

        if matched_chunk:
            # Extract snippet from chunk if possible
            lines = matched_chunk.content.splitlines()
            start_offset = max(0, cit.start_line - matched_chunk.start_line)
            end_offset = min(len(lines), cit.end_line - matched_chunk.start_line + 1)
            snippet = "\n".join(lines[start_offset:end_offset]) if lines else None

            valid_citations.append(
                Citation(
                    file_path=cit.file_path,
                    start_line=cit.start_line,
                    end_line=cit.end_line,
                    snippet=snippet,
                    chunk_id=matched_chunk.chunk_id,
                )
            )

    return valid_citations


# ==============================================================================
# Feature 13: Voice Conversational Prompt & Speech Cleaning
# ==============================================================================

VOICE_SYSTEM_PROMPT = """You are DevMind Voice Assistant, speaking on a direct voice call with a developer colleague.
Your response will be spoken aloud via text-to-speech through the user's speakers or headphones.

CRITICAL VOICE CONVERSATION RULES:
1. NATURAL SPOKEN WORDS ONLY: Speak naturally and warmly like a senior engineering teammate talking over audio.
2. ABSOLUTELY ZERO MARKDOWN OR SYNTAX: NEVER include markdown headers (#), asterisks (** or *), bullet points (- or *), numbered lists (1.), backticks (`code`), code blocks (```), or citation brackets like [File: ... Lines: ...]. Text-to-speech reads those symbols out loud, which ruins the spoken audio.
3. CONCISE & COMPLETE: Keep your response between 2 and 4 short, clear, complete sentences. Finish every sentence cleanly with a period. NEVER trail off with ellipses (...) or incomplete thoughts.
4. CODE EXPLANATION: Never read raw code listings or syntax. Describe what the code does conceptually in plain language. Mention key components or file names naturally (for example: "in the auth routes" or "the ingestion pipeline").
5. LANGUAGE & ACCURACY:
   - If the user asks in Hindi or Hinglish, reply naturally in clear, fluent conversational Hinglish.
   - If the user asks in English, reply in natural conversational English.
   - If the codebase evidence does not contain the answer, say warmly in one complete sentence that you couldn't find that in the indexed files and ask what else you can check.
"""


def clean_for_speech(text: str) -> str:
    """Removes any stray markdown, citation brackets, asterisks, or code fences before text-to-speech."""
    # Remove citation tags like [File: ... Lines: ...] or [path:10-20]
    t = re.sub(r"\[(?:File:\s*)?[^\]]+\]", "", text)
    # Remove code blocks
    t = re.sub(r"```[\s\S]*?```", "", t)
    # Remove backticks
    t = t.replace("`", "")
    # Remove bold/italic asterisks
    t = t.replace("**", "").replace("*", "")
    # Remove markdown headers (#, ##) and list bullets (- , * , 1. )
    t = re.sub(r"^[#\-\*\d\.\s]+\s", "", t, flags=re.MULTILINE)
    # Remove double quotes or awkward characters
    t = t.replace("###", "").replace("##", "").replace("#", "")
    # Collapse multiple whitespaces/newlines
    t = re.sub(r"\s+", " ", t).strip()
    return t


def build_voice_prompt(
    question: str,
    chunks: list[Union[CodeChunk, SearchResult]],
    history: Optional[list[ChatMessage]] = None,
    repo_name: Optional[str] = None,
    max_total_chars: Optional[int] = 8000,
) -> tuple[str, str]:
    """
    Builds the (system_prompt, user_prompt) tuple specifically tailored for spoken audio voice dialogue.
    """
    evidence_text = format_chunk_context(chunks, max_total_chars=max_total_chars)

    history_text = ""
    if history:
        history_lines: list[str] = []
        for msg in history[-4:]:  # Bound history to last 4 turns for spoken dialogue
            history_lines.append(f"{msg.role.upper()}: {msg.content}")
        history_text = (
            "--- RECENT SPOKEN DIALOGUE TURNS ---\n"
            + "\n".join(history_lines)
            + "\n------------------------------------\n\n"
        )

    repo_banner = f"REPOSITORY CONTEXT: {repo_name}\n" if repo_name else ""

    from ..retrieval.multilingual import detect_language
    lang = detect_language(question)
    lang_directive = ""
    if lang in ("hindi", "hinglish"):
        lang_directive = "\n- The developer spoke in Hindi/Hinglish. Reply in friendly conversational Hinglish."

    user_prompt = (
        f"{repo_banner}"
        f"{history_text}"
        f"--- RELEVANT CODEBASE CONTEXT ---\n"
        f"{evidence_text}\n"
        f"--------------------------------\n\n"
        f"DEVELOPER SPOKE:\n\"{question.strip()}\"\n\n"
        f"Synthesize a direct 2-4 sentence spoken answer for text-to-speech. Remember: NO markdown, NO asterisks, NO bullet points, NO citation brackets.{lang_directive}"
    )

    return VOICE_SYSTEM_PROMPT, user_prompt

