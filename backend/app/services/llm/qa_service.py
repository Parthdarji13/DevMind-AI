"""
End-to-end Question-Answering Service for DevMind AI.
Ref: PRD Section 6 (FR-07, FR-08, FR-09), Section 7; Step 21 of execution guide.
Connects hybrid retrieval, prompt contract, provider client, and citation verification.
"""
import logging
from typing import Optional

from ...models.chat import ChatRequest, ChatResponse, Citation, VoiceChatRequest, VoiceChatResponse
from ...models.chunk import CodeChunk
from ..indexing.storage import PersistentIndexStore
from ..retrieval.hybrid import HybridRetrievalManager
from ..retrieval.vector import RepositoryNotIndexedError
from .citation_validator import CitationValidator
from .client import BaseLLMProvider, get_llm_provider
from .conversation import ConversationManager, RepositoryContextMismatchError
from .prompt import (
    build_qa_prompt,
    build_voice_prompt,
    clean_for_speech,
    has_inference,
    is_abstention,
)

from .greeting import (
    extract_user_display_name,
    is_pure_greeting,
    extract_greeting_prefix,
    generate_greeting_response,
    is_hinglish_greeting,
)

logger = logging.getLogger(__name__)


def synthesize_tts_mp3(text: str, language: str = "english") -> Optional[str]:
    """Generates lifelike human speech audio via edge-tts, returning base64 encoded MP3."""
    import base64
    try:
        import edge_tts
    except ImportError:
        return None

    # Pick voice: natural Indian neural voice for Hindi/Hinglish, natural US voice for English
    if language in ("hindi", "hinglish"):
        voice = "hi-IN-MadhurNeural"
    else:
        voice = "en-US-GuyNeural"

    async def _gen():
        comm = edge_tts.Communicate(text, voice)
        chunks = []
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    try:
        import asyncio
        import concurrent.futures
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                audio_bytes = pool.submit(asyncio.run, _gen()).result(timeout=2.0)
        else:
            audio_bytes = asyncio.run(_gen())

        if audio_bytes:
            return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        logger.debug(f"edge-tts fast synthesis bypassed: {e}")

    return None


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

    def answer_question(self, request: ChatRequest, user: Optional[object] = None) -> ChatResponse:
        """Processes ChatRequest into grounded ChatResponse with citations and session context."""
        repo_id = request.repo_id
        question = request.question.strip()
        top_k = min(request.max_chunks, 15)

        # Resolve friendly user display name for personalized greetings
        user_name_val = request.user_name or (getattr(user, "name", None) if user and not getattr(user, "is_guest", False) else None)
        user_id_val = getattr(user, "id", None) or getattr(user, "user_id", None)
        user_email_val = getattr(user, "email", None)
        display_name = extract_user_display_name(user_name_val, user_id=user_id_val, email=user_email_val)

        # 1. Resolve session and bounded conversation history
        session_id = request.session_id
        if session_id:
            session_id, stored_history = self.conversation_manager.get_or_create_session(
                session_id, repo_id
            )
            effective_history = request.history if request.history else stored_history
        else:
            session_id, _ = self.conversation_manager.get_or_create_session(None, repo_id)
            effective_history = request.history

        bounded_history = self.conversation_manager.sanitize_and_bound_history(effective_history)

        # Pure Greeting Interception
        if is_pure_greeting(question):
            is_hinglish = is_hinglish_greeting(question)
            greeting_answer = generate_greeting_response(display_name, is_voice=False, is_hinglish=is_hinglish)
            if session_id:
                self.conversation_manager.record_turn(session_id, repo_id, question, greeting_answer)
            return ChatResponse(
                answer=greeting_answer,
                citations=[],
                abstained=False,
                inference_detected=False,
                retrieved_chunks_count=0,
                session_id=session_id,
            )

        # 2. Contextualize query for follow-up questions
        greeting_inquiry = extract_greeting_prefix(question)
        query_to_search = greeting_inquiry if greeting_inquiry else question
        retrieval_query = self.conversation_manager.contextualize_query(query_to_search, bounded_history)

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

        if greeting_inquiry and not answer.lower().startswith("hii") and not answer.lower().startswith("hi"):
            answer = f"Hii, {display_name}!\n\n{answer}"

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

    def answer_question_stream(
        self, request: ChatRequest, user: Optional[object] = None, user_id: Optional[str] = None
    ):
        """Generates real-time Server-Sent Events (SSE) for streaming answers progressively."""
        import json
        repo_id = request.repo_id
        question = request.question.strip()
        top_k = min(request.max_chunks, 15)

        # Resolve friendly user display name for personalized greetings
        actual_user_id = user_id or getattr(user, "id", None) or getattr(user, "user_id", None)
        user_name_val = request.user_name or (getattr(user, "name", None) if user and not getattr(user, "is_guest", False) else None)
        user_email_val = getattr(user, "email", None)
        display_name = extract_user_display_name(user_name_val, user_id=actual_user_id, email=user_email_val)

        # 1. Resolve session and bounded conversation history
        session_id = request.session_id
        if session_id:
            session_id, stored_history = self.conversation_manager.get_or_create_session(
                session_id, repo_id
            )
            effective_history = request.history if request.history else stored_history
        else:
            session_id, _ = self.conversation_manager.get_or_create_session(None, repo_id)
            effective_history = request.history

        bounded_history = self.conversation_manager.sanitize_and_bound_history(effective_history)

        # Pure Greeting Interception
        if is_pure_greeting(question):
            is_hinglish = is_hinglish_greeting(question)
            greeting_text = generate_greeting_response(display_name, is_voice=False, is_hinglish=is_hinglish)
            if session_id:
                self.conversation_manager.record_turn(session_id, repo_id, question, greeting_text)
            from ..db.mongo import MongoStorage, is_mongo_available
            if is_mongo_available():
                try:
                    MongoStorage.record_chat_turn(
                        repo_id=repo_id,
                        session_id=session_id,
                        user_message=question,
                        assistant_message=greeting_text,
                        citations=[],
                        user_id=actual_user_id,
                        inference_detected=False,
                        abstained=False,
                    )
                except Exception as e:
                    logger.warning(f"Failed to record streamed greeting to MongoDB: {e}")

            yield f"event: metadata\ndata: {json.dumps({'session_id': session_id, 'retrieved_chunks_count': 0})}\n\n"
            yield f"event: token\ndata: {json.dumps({'token': greeting_text})}\n\n"
            yield f"event: done\ndata: {json.dumps({'session_id': session_id, 'citations': [], 'abstained': False, 'inference_detected': False, 'answer': greeting_text})}\n\n"
            return

        # 2. Contextualize query
        greeting_inquiry = extract_greeting_prefix(question)
        query_to_search = greeting_inquiry if greeting_inquiry else question
        retrieval_query = self.conversation_manager.contextualize_query(query_to_search, bounded_history)

        # 3. Multilingual query expansion
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

            yield f"event: metadata\ndata: {json.dumps({'session_id': session_id, 'retrieved_chunks_count': 0})}\n\n"
            yield f"event: token\ndata: {json.dumps({'token': abstain_text})}\n\n"
            yield f"event: done\ndata: {json.dumps({'session_id': session_id, 'citations': [], 'abstained': True, 'inference_detected': False, 'answer': abstain_text})}\n\n"
            return

        # 6. Build prompt
        sys_prompt, user_prompt = build_qa_prompt(
            question=question,
            chunks=retrieved_chunks,
            history=bounded_history,
            repo_name=repo_id,
        )

        yield f"event: metadata\ndata: {json.dumps({'session_id': session_id, 'retrieved_chunks_count': len(retrieved_chunks)})}\n\n"

        # 7. Stream tokens
        provider = self._get_provider()
        accumulated_answer: list[str] = []

        if greeting_inquiry:
            prefix_tok = f"Hii, {display_name}!\n\n"
            accumulated_answer.append(prefix_tok)
            yield f"event: token\ndata: {json.dumps({'token': prefix_tok})}\n\n"

        stream_err: Optional[Exception] = None
        try:
            for token in provider.generate_stream(sys_prompt, user_prompt):
                accumulated_answer.append(token)
                yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            logger.error(f"Streaming token generation error: {e}", exc_info=True)
            stream_err = e

        # If generation yielded nothing (e.g. rate limit or API error), provide clear user feedback
        # rather than letting the UI show an empty white bubble
        non_prefix_tokens = accumulated_answer[1:] if greeting_inquiry else accumulated_answer
        if not non_prefix_tokens:
            err_str = str(stream_err).lower() if stream_err else ""
            if "429" in err_str or "rate limit" in err_str or "quota" in err_str:
                fallback_msg = (
                    "The AI model quota is temporarily reached on Google Gemini. "
                    "Please wait a few moments and try asking your question again."
                )
            else:
                fallback_msg = (
                    "I encountered a temporary issue generating a response from the codebase. "
                    "Please try asking your question again in a moment."
                )
            accumulated_answer.append(fallback_msg)
            yield f"event: token\ndata: {json.dumps({'token': fallback_msg})}\n\n"

        full_answer = "".join(accumulated_answer)

        # 8. Citation validation and completion
        validation_report = self.citation_validator.process_text_citations(
            full_answer, retrieved_chunks
        )
        validated_citations = validation_report.valid_citations

        if session_id:
            self.conversation_manager.record_turn(session_id, repo_id, question, full_answer)

        abstained = is_abstention(full_answer, has_citations=bool(validated_citations))
        inference_flag = has_inference(full_answer)

        # 9. Sync to MongoDB if available
        from ..db.mongo import MongoStorage, is_mongo_available
        if is_mongo_available():
            try:
                MongoStorage.record_chat_turn(
                    repo_id=repo_id,
                    session_id=session_id,
                    user_message=question,
                    assistant_message=full_answer,
                    citations=[c.model_dump() for c in validated_citations],
                    user_id=user_id,
                    inference_detected=inference_flag,
                    abstained=abstained,
                )
            except Exception as e:
                logger.warning(f"Failed to record streamed chat turn to MongoDB: {e}")

        done_payload = {
            "session_id": session_id,
            "citations": [c.model_dump() for c in validated_citations],
            "abstained": abstained,
            "inference_detected": inference_flag,
            "retrieved_chunks_count": len(retrieved_chunks),
            "answer": full_answer,
        }
        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

    def answer_voice_question(
        self, request: VoiceChatRequest, user: Optional[object] = None, user_id: Optional[str] = None
    ) -> VoiceChatResponse:
        """Processes VoiceChatRequest into a concise, spoken conversational response for TTS."""
        repo_id = request.repo_id
        question = request.question.strip()
        top_k = 6

        # Resolve friendly user display name for personalized greetings
        actual_user_id = user_id or getattr(user, "id", None) or getattr(user, "user_id", None)
        user_name_val = request.user_name or (getattr(user, "name", None) if user and not getattr(user, "is_guest", False) else None)
        user_email_val = getattr(user, "email", None)
        display_name = extract_user_display_name(user_name_val, user_id=actual_user_id, email=user_email_val)

        # 1. Resolve session and bounded conversation history
        session_id = request.session_id
        if session_id:
            session_id, stored_history = self.conversation_manager.get_or_create_session(
                session_id, repo_id
            )
            effective_history = request.history if request.history else stored_history
        else:
            session_id, _ = self.conversation_manager.get_or_create_session(None, repo_id)
            effective_history = request.history

        bounded_history = self.conversation_manager.sanitize_and_bound_history(effective_history)

        # Pure Greeting Interception
        if is_pure_greeting(question):
            is_hinglish = is_hinglish_greeting(question)
            spoken_greeting = generate_greeting_response(display_name, is_voice=True, is_hinglish=is_hinglish)
            if session_id:
                self.conversation_manager.record_turn(session_id, repo_id, question, spoken_greeting)
            from ..db.mongo import MongoStorage, is_mongo_available
            if is_mongo_available():
                try:
                    MongoStorage.record_chat_turn(
                        repo_id=repo_id,
                        session_id=session_id,
                        user_message=f"[Voice] {question}",
                        assistant_message=spoken_greeting,
                        citations=[],
                        user_id=actual_user_id,
                        inference_detected=False,
                        abstained=False,
                    )
                except Exception as e:
                    logger.warning(f"Failed to record voice greeting to MongoDB: {e}")
            lang = "hinglish" if is_hinglish else "english"
            audio_b64 = synthesize_tts_mp3(spoken_greeting, lang)
            return VoiceChatResponse(
                answer=spoken_greeting,
                session_id=session_id,
                cited_files=[],
                audio_base64=audio_b64,
            )

        # 2. Contextualize query
        greeting_inquiry = extract_greeting_prefix(question)
        query_to_search = greeting_inquiry if greeting_inquiry else question
        retrieval_query = self.conversation_manager.contextualize_query(query_to_search, bounded_history)

        # 3. Multilingual query expansion
        from ..retrieval.multilingual import detect_language, expand_multilingual_query
        search_query = expand_multilingual_query(retrieval_query)

        # 4. Retrieve evidence chunks
        try:
            results = self.retrieval_manager.retrieve(
                repo_id=repo_id,
                query=search_query,
                top_k=8,
            )
        except RepositoryNotIndexedError:
            raise
        except Exception as e:
            logger.error(f"Error retrieving chunks for voice repo {repo_id}: {e}", exc_info=True)
            results = []

        retrieved_chunks = [r.chunk for r in results]

        # Architectural root file booster for comprehensive overviews
        q_lower = question.lower()
        is_general_query = any(k in q_lower for k in [
            "project", "architecture", "overview", "what is", "kya hai", "explain",
            "kaise", "samjhao", "intro", "structure", "stack", "about"
        ])
        if is_general_query:
            try:
                store = self.retrieval_manager.storage_manager.get_store(repo_id)
                all_chunks = store.load_chunks()
                root_priority = [
                    "readme.md", "package.json", "requirements.txt",
                    "main.py", "app.py", "index.js", "app.js", "server.js"
                ]
                for chunk in all_chunks:
                    fn = chunk.file_path.lower()
                    if any(fn.endswith(rp) or fn == rp for rp in root_priority):
                        if not any(c.chunk_id == chunk.chunk_id for c in retrieved_chunks):
                            retrieved_chunks.insert(0, chunk)
                        if len(retrieved_chunks) >= 10:
                            break
            except Exception as e:
                logger.debug(f"Root file boost skipped for voice: {e}")

        # 5. If no chunks retrieved, abstain in voice style
        lang = detect_language(question)
        if not retrieved_chunks:
            if lang in ("hindi", "hinglish"):
                spoken_answer = (
                    "Mujhe indexed files me is baare me koi jankari nahi mili. "
                    "Kya aap kisi specific file ya component ke bare me puchna chahenge?"
                )
            else:
                spoken_answer = (
                    "I couldn't find details about that in the indexed files. "
                    "Could you ask about a specific component or feature?"
                )
            audio_b64 = synthesize_tts_mp3(spoken_answer, lang)
            return VoiceChatResponse(
                answer=spoken_answer,
                session_id=session_id,
                cited_files=[],
                audio_base64=audio_b64,
            )

        # 6. Build spoken voice prompt
        sys_prompt, user_prompt = build_voice_prompt(
            question=question,
            chunks=retrieved_chunks,
            history=bounded_history,
            repo_name=repo_id,
        )

        # 7. Generate response via LLM
        provider = self._get_provider()
        try:
            raw_answer = provider.generate_response(sys_prompt, user_prompt)
        except LLMRateLimitError:
            raw_answer = (
                "The AI service is experiencing a temporary rate limit. "
                "Please wait a few seconds and try speaking your question again."
            )
        except Exception as e:
            logger.error(f"Error generating voice response: {e}", exc_info=True)
            raw_answer = (
                "I encountered a temporary issue generating a response from the codebase. "
                "Please try speaking your question again."
            )

        # 8. Clean response specifically for text-to-speech
        spoken_answer = clean_for_speech(raw_answer)
        if greeting_inquiry and not spoken_answer.lower().startswith("hii") and not spoken_answer.lower().startswith("hi"):
            spoken_answer = f"Hii, {display_name}! {spoken_answer}"

        # 9. Extract key files referenced in chunks for UI chips
        seen_files: list[str] = []
        for c in retrieved_chunks:
            if c.file_path not in seen_files:
                seen_files.append(c.file_path)
            if len(seen_files) >= 4:
                break

        # 10. Record turn in session and Mongo
        if session_id:
            self.conversation_manager.record_turn(session_id, repo_id, question, spoken_answer)

        from ..db.mongo import MongoStorage, is_mongo_available
        if is_mongo_available():
            try:
                MongoStorage.record_chat_turn(
                    repo_id=repo_id,
                    session_id=session_id,
                    user_message=f"[Voice] {question}",
                    assistant_message=spoken_answer,
                    citations=[],
                    user_id=actual_user_id,
                    inference_detected=False,
                    abstained=False,
                )
            except Exception as e:
                logger.warning(f"Failed to record voice chat turn to MongoDB: {e}")

        # 11. Synthesize lifelike speech audio MP3
        audio_b64 = synthesize_tts_mp3(spoken_answer, lang)

        return VoiceChatResponse(
            answer=spoken_answer,
            session_id=session_id,
            cited_files=seen_files,
            audio_base64=audio_b64,
        )


