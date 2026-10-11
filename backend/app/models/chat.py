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


class ChatResponse(BaseModel):
    """Evidence-grounded response with verified citations and inference markers."""
    answer: str = Field(..., description="Synthesized answer text")
    citations: list[Citation] = Field(default_factory=list, description="Extracted and verified citations")
    abstained: bool = Field(default=False, description="True if evidence was insufficient to answer")
    inference_detected: bool = Field(default=False, description="True if answer includes inference markers")
    retrieved_chunks_count: int = Field(default=0, description="Number of evidence chunks provided to LLM")
