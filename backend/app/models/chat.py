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
