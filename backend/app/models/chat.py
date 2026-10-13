"""
Chat, citation, and QA data models.
Ref: PRD Section 6 (FR-07, FR-08, FR-09), Section 7, Section 8; Step 20 of execution guide.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Specific line-range citation from a verified source file."""
    file_path: str = Field(..., description="Repository-relative file path")
    start_line: int = Field(..., ge=1, description="Starting line number (1-indexed)")
    end_line: int = Field(..., ge=1, description="Ending line number (1-indexed)")
    snippet: Optional[str] = Field(None, description="Verbatim code snippet cited")
    chunk_id: Optional[str] = Field(None, description="Originating chunk identifier")


class ChatMessage(BaseModel):
    """Single message in a conversational thread."""
    role: Literal["user", "assistant", "system"] = Field(..., description="Message author role")
    content: str = Field(..., description="Message text content")


class ChatRequest(BaseModel):
    """Payload for asking a question about an indexed codebase."""
    repo_id: str = Field(..., description="Identifier of the indexed repository")
    question: str = Field(..., min_length=1, max_length=2000, description="User's query")
    history: list[ChatMessage] = Field(default_factory=list, description="Prior conversation context")
    max_chunks: int = Field(default=8, ge=1, le=25, description="Maximum evidence chunks to retrieve")
    session_id: Optional[str] = Field(None, description="Optional conversation session ID")
    user_name: Optional[str] = Field(None, description="Optional display name or username")



class ChatResponse(BaseModel):
    """Evidence-grounded response with verified citations and inference markers."""
    answer: str = Field(..., description="Synthesized answer text")
    citations: list[Citation] = Field(default_factory=list, description="Extracted and verified citations")
    abstained: bool = Field(default=False, description="True if evidence was insufficient to answer")
    inference_detected: bool = Field(default=False, description="True if answer includes inference markers")
    retrieved_chunks_count: int = Field(default=0, description="Number of evidence chunks provided to LLM")
    session_id: Optional[str] = Field(None, description="Conversation session ID")


class SuggestedQuestion(BaseModel):
    """Repository-derived suggested inquiry for codebase discovery."""
    question: str = Field(..., description="Suggested inquiry text")
    category: str = Field(..., description="Category: Architecture, API & Routing, Data & Models, Security & Auth, or Core Logic")
    derived_from: str = Field(..., description="File path or symbol name from which inquiry was derived")
    is_verified: bool = Field(
        default=False,
        description="Explicit notice: suggestions are exploratory inquiries, verified only upon retrieval",
    )


class SuggestedQuestionsResponse(BaseModel):
    """Collection of repository-derived suggested questions."""
    repo_id: str = Field(..., description="Repository identifier")
    suggestions: list[SuggestedQuestion] = Field(default_factory=list, description="List of repository-derived questions")
    total_chunks_analyzed: int = Field(default=0, description="Number of indexed code chunks inspected")
    languages_detected: list[str] = Field(default_factory=list, description="Detected programming languages")


class ChatFeedbackRequest(BaseModel):
    """Payload for submitting user thumbs-up/down feedback and citation quality reports."""
    repo_id: str = Field(..., description="Repository identifier")
    message_id: Optional[str] = Field(None, description="Message identifier")
    session_id: Optional[str] = Field(None, description="Conversation session identifier")
    rating: Literal["up", "down"] = Field(..., description="'up' for thumbs up, 'down' for thumbs down")
    feedback_tag: Optional[Literal["correct", "wrong_source", "hallucination", "incomplete", "other"]] = Field(
        None, description="Classification of the feedback issue"
    )
    comment: Optional[str] = Field(None, max_length=1000, description="Optional developer comments")


# ==============================================================================
# Feature 8: Flow Trace Models
# ==============================================================================

class FlowTraceStep(BaseModel):
    """Single step in a traced execution path."""
    step_number: int = Field(..., description="Step sequence index (1-based)")
    title: str = Field(..., description="Action title of this step")
    file_path: str = Field(..., description="Relative file path where logic executes")
    start_line: int = Field(..., description="Starting line number")
    end_line: int = Field(..., description="Ending line number")
    function_or_symbol: Optional[str] = Field(None, description="Function, class, or symbol name")
    description: str = Field(..., description="Detailed explanation of execution at this step")


class FlowTraceRequest(BaseModel):
    """Payload to trace a multi-step execution flow."""
    repo_id: str = Field(..., description="Repository identifier")
    flow_query: str = Field(..., min_length=2, max_length=500, description="Flow to trace (e.g. 'user login', 'zip ingestion')")


class FlowTraceResponse(BaseModel):
    """Structured step-by-step trace of a code flow with Mermaid sequence diagram."""
    flow_title: str = Field(..., description="Title of the traced flow")
    summary: str = Field(..., description="High-level architectural overview of the flow")
    steps: list[FlowTraceStep] = Field(default_factory=list, description="Ordered execution steps")
    mermaid_diagram: str = Field(..., description="Mermaid sequenceDiagram representation of the flow")
    citations: list[Citation] = Field(default_factory=list, description="Evidence citations for the flow")


# ==============================================================================
# Feature 9: Onboarding Architecture Doc Models
# ==============================================================================

class OnboardingDocRequest(BaseModel):
    """Payload to generate a comprehensive onboarding architecture document."""
    repo_id: str = Field(..., description="Repository identifier")


class OnboardingDocResponse(BaseModel):
    """Generated onboarding architecture document with module breakdown and verified citations."""
    repo_id: str = Field(..., description="Repository identifier")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Full Markdown content of onboarding guide")
    summary: str = Field(..., description="2-3 sentence executive summary")
    file_count: int = Field(default=0, description="Indexed files analyzed")
    languages: list[str] = Field(default_factory=list, description="Primary languages detected")


# ==============================================================================
# Feature 11: Architecture Dependency Map Models
# ==============================================================================

class ArchitectureMapNode(BaseModel):
    """Module or layer node in the architectural graph."""
    id: str = Field(..., description="Unique module or directory identifier")
    label: str = Field(..., description="Human-readable module name")
    module_type: str = Field(..., description="Layer category: api, services, models, db, core, utils, other")
    file_count: int = Field(default=1, description="Number of files inside module")
    line_count: int = Field(default=0, description="Total LOC in module")
    description: Optional[str] = Field(None, description="Inferred role of this module")
    key_files: list[str] = Field(default_factory=list, description="Top key files in this module")


class ArchitectureMapEdge(BaseModel):
    """Directed dependency or import edge between modules."""
    source: str = Field(..., description="Source module ID")
    target: str = Field(..., description="Target module ID (imported)")
    relationship: str = Field(default="imports", description="Dependency type: imports, calls, depends_on")
    import_count: int = Field(default=1, description="Number of detected cross-module imports")


class ArchitectureMapResponse(BaseModel):
    """Interactive architectural dependency graph of the codebase."""
    repo_id: str = Field(..., description="Repository identifier")
    nodes: list[ArchitectureMapNode] = Field(default_factory=list, description="Architectural nodes")
    edges: list[ArchitectureMapEdge] = Field(default_factory=list, description="Inter-module dependency edges")
    total_modules: int = Field(default=0, description="Total identified modules")


# ==============================================================================
# Feature 12: Learning Mode & Quiz Models
# ==============================================================================

class QuizQuestion(BaseModel):
    """Codebase understanding quiz question."""
    id: str = Field(..., description="Unique question identifier")
    question: str = Field(..., description="The quiz question text")
    options: list[str] = Field(..., min_length=4, max_length=4, description="4 multiple-choice options")
    correct_index: int = Field(..., ge=0, le=3, description="Index of the correct answer (0-3)")
    hint: str = Field(..., description="Helpful clue for learners")
    explanation: str = Field(..., description="Detailed explanation of the correct answer citing code")
    file_path: str = Field(..., description="Source file tested")
    start_line: int = Field(..., description="Source line start")
    end_line: int = Field(..., description="Source line end")


class QuizResponse(BaseModel):
    """Collection of quiz questions for learning mode."""
    repo_id: str = Field(..., description="Repository identifier")
    questions: list[QuizQuestion] = Field(default_factory=list, description="Questions generated for this repo")
    total_questions: int = Field(default=0, description="Count of questions")


# ==============================================================================
# Feature 13: Dedicated Voice Conversation Mode
# ==============================================================================

class VoiceChatRequest(BaseModel):
    """Payload for real-time conversational voice interaction with indexed codebase."""
    repo_id: str = Field(..., description="Identifier of the indexed repository")
    question: str = Field(..., min_length=1, max_length=2000, description="Spoken question from developer")
    history: list[ChatMessage] = Field(default_factory=list, description="Prior conversational context turns")
    session_id: Optional[str] = Field(None, description="Optional conversation session ID")
    user_name: Optional[str] = Field(None, description="Optional display name or username")



class VoiceChatResponse(BaseModel):
    """Clean conversational voice answer synthesized for spoken audio TTS output."""
    answer: str = Field(..., description="Clean, spoken conversational answer without markdown, asterisks, or citation brackets")
    session_id: Optional[str] = Field(None, description="Conversation session ID")
    cited_files: list[str] = Field(default_factory=list, description="Repository files referenced in the answer")
    audio_base64: Optional[str] = Field(None, description="Base64 encoded lifelike MP3 speech audio")



