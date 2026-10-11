"""
Code chunk and line metadata models.
Ref: PRD Section 6 (FR-04, FR-07), Section 8; Step 14 of execution guide.
"""
from typing import Optional
from pydantic import BaseModel, Field


class CodeChunk(BaseModel):
    chunk_id: str = Field(..., description="Unique deterministic chunk identifier")
    repo_id: str = Field(..., description="Repository ID this chunk belongs to")
    file_path: str = Field(..., description="Repository-relative file path")
    language: str = Field(..., description="Programming language or format")
    start_line: int = Field(..., ge=1, description="1-indexed starting line number (inclusive)")
    end_line: int = Field(..., ge=1, description="1-indexed ending line number (inclusive)")
    content: str = Field(..., description="Source code text of the chunk")
    chunk_index: int = Field(..., ge=0, description="Sequential index within the file")
    symbol_name: Optional[str] = Field(None, description="Enclosing class, function, or symbol name")
    line_count: int = Field(..., ge=1, description="Total lines in this chunk")
    char_count: int = Field(..., ge=1, description="Total characters in chunk content")
