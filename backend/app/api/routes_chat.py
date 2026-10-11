"""
Chat API routes for evidence-grounded codebase Q&A.
Ref: PRD Section 6 (FR-07, FR-08, FR-09), Section 7, Section 8, Section 9; Step 21 of execution guide.
Validates repository ID, question, and history; returns grounded responses with citations.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from ..models.chat import (
    ChatRequest,
    ChatResponse,
    SuggestedQuestionsResponse,
)
from ..services.indexing.storage import PersistentIndexStore
from ..services.llm.suggestions import SuggestionService
from ..services.llm.client import (
    LLMAPIError,
    LLMConfigurationError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from ..services.llm.conversation import RepositoryContextMismatchError
from ..services.llm.qa_service import QAService
from ..services.retrieval.vector import RepositoryNotIndexedError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])

def get_qa_service() -> QAService:
    return QAService()


@router.post(
    "/api/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask an evidence-grounded question about an indexed codebase",
)
async def ask_question(
    request: ChatRequest,
    qa_service: QAService = Depends(get_qa_service),
) -> ChatResponse:
    # 1. Validate question input
    q_stripped = request.question.strip()
    if not q_stripped:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question cannot be empty or whitespace.",
        )
    if len(q_stripped) > 2000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question exceeds maximum allowed length of 2000 characters.",
        )

    # 2. Validate repository exists and is indexed
    repo_id = request.repo_id.strip()
    if not repo_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository ID must be specified.",
        )

    store = qa_service.retrieval_manager.storage_manager.get_store(repo_id)
    if not store.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repo_id}' has not been indexed yet or index is missing.",
        )

    # 3. Process question through QA service
    try:
        response = qa_service.answer_question(request)
        return response
    except RepositoryNotIndexedError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repo_id}' is not indexed.",
        )
    except RepositoryContextMismatchError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LLMRateLimitError as e:
        logger.warning(f"LLM rate limit encountered: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="LLM provider rate limit exceeded. Please retry in a few moments.",
        )
    except LLMTimeoutError as e:
        logger.warning(f"LLM request timed out: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM provider request timed out. Please retry with a more specific question.",
        )
    except LLMConfigurationError as e:
        logger.error(f"LLM configuration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM provider service is not properly configured. Check server credentials.",
        )
    except LLMAPIError as e:
        logger.error(f"LLM API provider error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="External LLM provider returned an error.",
        )
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the question.",
        )


@router.get(
    "/api/chat/suggested-questions/{repo_id}",
    response_model=SuggestedQuestionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get repository-derived suggested questions based on indexed files and symbols",
)
async def get_suggested_questions(repo_id: str) -> SuggestedQuestionsResponse:
    """
    Derives suggested inquiries tailored directly to repository files, symbols, and entry points.
    Fulfills Step 29: derived from verified indexed files, explicitly clarifying suggestions are exploratory.
    """
    repo_id_clean = repo_id.strip()
    if not repo_id_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository ID cannot be empty.",
        )

    store = PersistentIndexStore(repo_id_clean)
    if not store.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repo_id_clean}' has not been indexed yet or index is missing.",
        )

    suggester = SuggestionService()
    return suggester.generate_suggestions(repo_id_clean)
