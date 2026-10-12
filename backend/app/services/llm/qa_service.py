"""
End-to-end Question-Answering Service for DevMind AI.
Ref: PRD Section 6 (FR-07, FR-08, FR-09), Section 7; Step 21 of execution guide.
Connects hybrid retrieval, prompt contract, provider client, and citation verification.
"""
import logging
from typing import Optional

from ...models.chat import ChatRequest, ChatResponse, Citation
from ...models.chunk import CodeChunk
from ..indexing.storage import PersistentIndexStore
from ..retrieval.hybrid import HybridRetrievalManager
from ..retrieval.vector import RepositoryNotIndexedError
from .citation_validator import CitationValidator
from .client import BaseLLMProvider, get_llm_provider
from .conversation import ConversationManager, RepositoryContextMismatchError
from .prompt import (
    build_qa_prompt,
    has_inference,
    is_abstention,
)

logger = logging.getLogger(__name__)


class QAService:
    """Orchestrates hybrid retrieval, prompt synthesis, LLM generation, and citation validation."""

    def __init__(
        self,
        retrieval_manager: Optional[HybridRetrievalManager] = None,
        llm_provider: Optional[BaseLLMProvider] = None,
        citation_validator: Optional[CitationValidator] = None,
        conversation_manager: Optional[ConversationManager] = None,
    ):
        self.retrieval_manager = retrieval_manager or HybridRetrievalManager()
        self.llm_provider = llm_provider
        self.citation_validator = citation_validator or CitationValidator()
        self.conversation_manager = conversation_manager or ConversationManager()

    def _get_provider(self) -> BaseLLMProvider:
        if self.llm_provider is not None:
            return self.llm_provider
        return get_llm_provider()

    def answer_question(self, request: ChatRequest) -> ChatResponse:
        """Processes ChatRequest into grounded ChatResponse with citations and session context."""
        repo_id = request.repo_id
        question = request.question.strip()
        top_k = min(request.max_chunks, 15)

        # 1. Resolve session and bounded conversation history
        session_id = request.session_id
        if session_id:
            session_id, stored_history = self.conversation_manager.get_or_create_session(
                session_id, repo_id
            )
            effective_history = request.history if request.history else stored_history
        else:
            effective_history = request.history

        bounded_history = self.conversation_manager.sanitize_and_bound_history(effective_history)

        # 2. Contextualize query for follow-up questions
        retrieval_query = self.conversation_manager.contextualize_query(question, bounded_history)

        # 3. Multilingual query expansion for hybrid retrieval (Step 30)
        from ..retrieval.multilingual import detect_language, expand_multilingual_query
        search_query = expand_multilingual_query(retrieval_query)

        # 4. Retrieve evidence chunks
        try:
            results = self.retrieval_manager.retrieve(
                repo_id=repo_id,
                query=search_query,
                top_k=top_k,
            )
        except RepositoryNotIndexedError:
            raise
        except Exception as e:
            logger.error(f"Error retrieving chunks for repo {repo_id}: {e}", exc_info=True)
            results = []

        retrieved_chunks = [r.chunk for r in results]

        # 5. If no chunks retrieved, abstain immediately in appropriate language
        if not retrieved_chunks:
            lang = detect_language(question)
            if lang == "hindi":
                abstain_text = "दिए गए कोडबेस साक्ष्य में इस प्रश्न का उत्तर देने के लिए पर्याप्त जानकारी नहीं है।"
            elif lang == "hinglish":
                abstain_text = "Retrieved codebase evidence me is question ka answer dene ke liye paryapt information nahi hai."
            else:
                abstain_text = "The retrieved codebase evidence does not contain sufficient information to answer this question."

            return ChatResponse(
                answer=abstain_text,
                citations=[],
                abstained=True,
                inference_detected=False,
                retrieved_chunks_count=0,
                session_id=session_id,
            )

        # 5. Build grounded prompt tuple with bounded history
        sys_prompt, user_prompt = build_qa_prompt(
            question=question,
            chunks=retrieved_chunks,
            history=bounded_history,
            repo_name=repo_id,
        )

        # 6. Generate answer via LLM
        provider = self._get_provider()
        answer = provider.generate_response(sys_prompt, user_prompt)

        # 7. Extract and strictly validate citations against retrieved chunks
        validation_report = self.citation_validator.process_text_citations(
            answer, retrieved_chunks
        )
        validated_citations = validation_report.valid_citations

        # 8. Never fabricate un-cited chunks: only genuinely cited references are included
        # (Fix for citation integrity audit: do not force retrieved_chunks[0] if model did not cite it)

        # 9. Record completed turn in session if session_id active
        if session_id:
            self.conversation_manager.record_turn(session_id, repo_id, question, answer)

        # 10. Check flags
        abstained = is_abstention(answer, has_citations=bool(validated_citations))
        inference_flag = has_inference(answer)

        return ChatResponse(
            answer=answer,
            citations=validated_citations,
            abstained=abstained,
            inference_detected=inference_flag,
            retrieved_chunks_count=len(retrieved_chunks),
            session_id=session_id,
        )
