"""
Chat API routes for evidence-grounded codebase Q&A.
Ref: PRD Section 6 (FR-07, FR-08, FR-09), Section 7, Section 8, Section 9; Step 21 of execution guide.
Validates repository ID, question, and history; returns grounded responses with citations.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ..models.chat import (
    ChatRequest,
    ChatResponse,
    ChatFeedbackRequest,
    SuggestedQuestionsResponse,
    FlowTraceRequest,
    FlowTraceResponse,
    OnboardingDocRequest,
    OnboardingDocResponse,
    ArchitectureMapResponse,
    QuizResponse,
    VoiceChatRequest,
    VoiceChatResponse,
    RepoFilesResponse,
    RepoFileInfo,
)
from ..services.indexing.storage import PersistentIndexStore
from ..services.llm.advanced_features import AdvancedFeaturesService
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
from ..services.auth.jwt_handler import UserContext, get_current_user
from ..services.auth.access_control import require_repo_access
from ..services.db.mongo import MongoStorage, is_mongo_available

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])

def get_qa_service() -> QAService:
    return QAService()

def get_advanced_features_service() -> AdvancedFeaturesService:
    return AdvancedFeaturesService()


@router.post(
    "/api/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask an evidence-grounded question about an indexed codebase",
)
async def ask_question(
    request: ChatRequest,
    user: UserContext = Depends(get_current_user),
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

    # 2. Validate repository exists, is indexed, and authorized
    repo_id = request.repo_id.strip()
    if not repo_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository ID must be specified.",
        )

    require_repo_access(repo_id, user)

    store = qa_service.retrieval_manager.storage_manager.get_store(repo_id)
    if not store.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repo_id}' has not been indexed yet or index is missing.",
        )

    # 3. Process question through QA service
    try:
        response = qa_service.answer_question(request, user=user)

        # Record completed chat turn in MongoDB if available
        if is_mongo_available():
            try:
                MongoStorage.record_chat_turn(
                    repo_id=repo_id,
                    session_id=response.session_id or request.session_id or "default",
                    user_message=request.question,
                    assistant_message=response.answer,
                    citations=[c.model_dump() for c in response.citations],
                    user_id=user.id if user else None,
                    inference_detected=response.inference_detected,
                    abstained=response.abstained,
                )
            except Exception as e:
                logger.warning(f"Failed to record chat turn in MongoDB: {e}")

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
        err_text = str(e)
        if "503" in err_text or "high demand" in err_text.lower():
            detail_msg = "The AI model is experiencing temporary high demand (HTTP 503). Please retry in a few moments."
        else:
            detail_msg = f"External LLM provider returned an error: {err_text[:120]}"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail_msg,
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
async def get_suggested_questions(
    repo_id: str,
    user: UserContext = Depends(get_current_user),
) -> SuggestedQuestionsResponse:
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

    require_repo_access(repo_id_clean, user)

    store = PersistentIndexStore(repo_id_clean)
    if not store.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repo_id_clean}' has not been indexed yet or index is missing.",
        )

    suggester = SuggestionService()
    return suggester.generate_suggestions(repo_id_clean)


@router.get(
    "/api/chat/files/{repo_id}",
    response_model=RepoFilesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all indexed files in the repository for interactive code explorer",
)
def get_repository_files(
    repo_id: str,
    user: UserContext = Depends(get_current_user),
    qa_service: QAService = Depends(get_qa_service),
) -> RepoFilesResponse:
    """Returns all indexed source files with metadata for the interactive sidebar file explorer."""
    repo_id_clean = repo_id.strip()
    if not repo_id_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository ID cannot be empty.",
        )

    require_repo_access(repo_id_clean, user)

    store = qa_service.retrieval_manager.storage_manager.get_store(repo_id_clean)
    if not store.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repo_id_clean}' has not been indexed yet.",
        )

    chunks = store.get_chunks()
    file_map: dict[str, dict] = {}
    for c in chunks:
        fp = c.file_path
        if fp not in file_map:
            file_map[fp] = {
                "chunk_count": 0,
                "max_line": 0,
                "language": getattr(c, "language", None) or "text",
            }
        file_map[fp]["chunk_count"] += 1
        if c.end_line > file_map[fp]["max_line"]:
            file_map[fp]["max_line"] = c.end_line

    files_list = [
        RepoFileInfo(
            file_path=fp,
            line_count=info["max_line"],
            chunk_count=info["chunk_count"],
            language=info["language"],
        )
        for fp, info in sorted(file_map.items(), key=lambda x: x[0].lower())
    ]

    return RepoFilesResponse(
        repo_id=repo_id_clean,
        total_files=len(files_list),
        files=files_list,
    )


@router.get(
    "/history/{repo_id}",
    summary="Get persistent chat history for a repository from MongoDB",
)
def get_chat_history(
    repo_id: str,
    session_id: Optional[str] = None,
    user: UserContext = Depends(get_current_user),
):
    """Retrieves recorded chat turns for a repository from MongoDB if available."""
    repo_id_clean = repo_id.strip()
    require_repo_access(repo_id_clean, user)
    if is_mongo_available():
        return MongoStorage.get_chat_history(repo_id_clean, session_id)
    return []


@router.post(
    "/api/chat/stream",
    summary="Ask a question and stream answers progressively as real-time Server-Sent Events (SSE)",
)
async def chat_question_stream(
    request: ChatRequest,
    user: UserContext = Depends(get_current_user),
    qa_service: QAService = Depends(get_qa_service),
):
    # Validate question and length
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

    repo_id = request.repo_id.strip()
    if not repo_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository ID must be specified.",
        )

    require_repo_access(repo_id, user)

    store = qa_service.retrieval_manager.storage_manager.get_store(repo_id)
    if not store.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repo_id}' has not been indexed yet or index is missing.",
        )

    generator = qa_service.answer_question_stream(request, user=user, user_id=user.id if user else None)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/api/chat/feedback",
    summary="Submit user satisfaction rating (thumbs up/down) and quality reports",
)
def submit_chat_feedback(
    feedback: ChatFeedbackRequest,
    user: UserContext = Depends(get_current_user),
):
    """Stores user thumbs-up/down ratings and quality reports in MongoDB Atlas."""
    require_repo_access(feedback.repo_id, user)
    record = feedback.model_dump()
    record["user_id"] = user.id if user else None

    saved = False
    if is_mongo_available():
        saved = MongoStorage.record_feedback(record)

    return {
        "status": "success",
        "saved_to_mongo": saved,
        "message": "Feedback submitted successfully. Thank you!",
    }


@router.post(
    "/api/chat/flow-trace",
    response_model=FlowTraceResponse,
    summary="Trace a step-by-step execution path through codebase with Mermaid sequence diagram (Feature 8)",
)
def get_flow_trace(
    request: FlowTraceRequest,
    user: UserContext = Depends(get_current_user),
    service: AdvancedFeaturesService = Depends(get_advanced_features_service),
) -> FlowTraceResponse:
    require_repo_access(request.repo_id, user)
    return service.trace_flow(request.repo_id, request.flow_query)


@router.post(
    "/api/chat/onboarding-doc",
    response_model=OnboardingDocResponse,
    summary="Generate an onboarding architecture document with verified citations (Feature 9)",
)
def get_onboarding_doc(
    request: OnboardingDocRequest,
    user: UserContext = Depends(get_current_user),
    service: AdvancedFeaturesService = Depends(get_advanced_features_service),
) -> OnboardingDocResponse:
    require_repo_access(request.repo_id, user)
    return service.generate_onboarding_doc(request.repo_id)


@router.get(
    "/api/chat/architecture-map/{repo_id}",
    response_model=ArchitectureMapResponse,
    summary="Get architectural dependency graph and module breakdown (Feature 11)",
)
def get_architecture_map(
    repo_id: str,
    user: UserContext = Depends(get_current_user),
    service: AdvancedFeaturesService = Depends(get_advanced_features_service),
) -> ArchitectureMapResponse:
    require_repo_access(repo_id, user)
    return service.build_architecture_map(repo_id)


@router.get(
    "/api/chat/quiz/{repo_id}",
    response_model=QuizResponse,
    summary="Generate codebase understanding quiz for learning mode (Feature 12)",
)
def get_learning_quiz(
    repo_id: str,
    user: UserContext = Depends(get_current_user),
    service: AdvancedFeaturesService = Depends(get_advanced_features_service),
) -> QuizResponse:
    require_repo_access(repo_id, user)
    return service.generate_learning_quiz(repo_id)


# ==============================================================================
# Feature 13: Dedicated Spoken Voice Interaction Endpoint
# ==============================================================================

@router.post(
    "/api/chat/voice",
    response_model=VoiceChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Spoken conversational voice Q&A without markdown or citation brackets (Feature 13)",
)
async def ask_voice_question(
    request: VoiceChatRequest,
    user: UserContext = Depends(get_current_user),
    qa_service: QAService = Depends(get_qa_service),
) -> VoiceChatResponse:
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

    repo_id = request.repo_id.strip()
    if not repo_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository ID must be specified.",
        )

    require_repo_access(repo_id, user)

    store = qa_service.retrieval_manager.storage_manager.get_store(repo_id)
    if not store.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repo_id}' has not been indexed yet or index is missing.",
        )

    try:
        user_identifier = getattr(user, "id", None) or getattr(user, "user_id", None)
        response = qa_service.answer_voice_question(request, user=user, user_id=user_identifier)
        return response
    except RepositoryNotIndexedError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repo_id}' is not indexed.",
        )
    except LLMRateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"LLM rate limit reached: {e}",
        )
    except LLMTimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"LLM request timed out: {e}",
        )
    except Exception as e:
        logger.error(f"Error answering voice question for repo '{repo_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error generating voice response: {str(e)}",
        )




