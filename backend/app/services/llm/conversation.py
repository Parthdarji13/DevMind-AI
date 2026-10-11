"""
Multi-turn conversation management and context resolution for DevMind AI.
Ref: PRD Section 6 (FR-08), Section 7, Section 8; Step 23 of execution guide.
Enforces:
1. Multi-question sessions without re-indexing or re-uploading.
2. Bounding conversation history to avoid prompt overflow.
3. Strict repository isolation across sessions.
4. Anaphora resolution for follow-up questions (e.g. "what does it return?").
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Optional
import uuid

from ...models.chat import ChatMessage


@dataclass
class ConversationSession:
    session_id: str
    repo_id: str
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RepositoryContextMismatchError(Exception):
    """Raised when a multi-turn conversation session is used across different repositories."""
    pass


class ConversationManager:
    """Manages multi-turn conversation sessions, history bounds, and follow-up contextualization."""

    ANAPHORIC_PATTERNS = [
        re.compile(r"\b(it|its|this|that|these|those|the function|the method|the class)\b", re.IGNORECASE),
    ]

    def __init__(self, max_turns: int = 6, max_history_chars: int = 4000):
        self.max_turns = max_turns
        self.max_history_chars = max_history_chars
        self._sessions: dict[str, ConversationSession] = {}

    def get_or_create_session(
        self,
        session_id: Optional[str],
        repo_id: str,
    ) -> tuple[str, list[ChatMessage]]:
        """
        Retrieves existing session or initializes a new one.
        Enforces strict repository isolation.
        """
        if not session_id:
            new_id = f"sess_{uuid.uuid4().hex[:12]}"
            sess = ConversationSession(session_id=new_id, repo_id=repo_id)
            self._sessions[new_id] = sess
            return new_id, []

        sess = self._sessions.get(session_id)
        if not sess:
            sess = ConversationSession(session_id=session_id, repo_id=repo_id)
            self._sessions[session_id] = sess
            return session_id, []

        # Enforce repository isolation
        if sess.repo_id != repo_id:
            raise RepositoryContextMismatchError(
                f"Session '{session_id}' is bound to repository '{sess.repo_id}', "
                f"and cannot be used for repository '{repo_id}'."
            )

        return session_id, list(sess.messages)

    def record_turn(
        self,
        session_id: str,
        repo_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        """Appends a completed question-answer turn to the session and bounds history."""
        sess_id, _ = self.get_or_create_session(session_id, repo_id)
        sess = self._sessions[sess_id]

        sess.messages.append(ChatMessage(role="user", content=user_message))
        sess.messages.append(ChatMessage(role="assistant", content=assistant_message))
        sess.updated_at = datetime.now(timezone.utc).isoformat()

        # Bound history to max_turns
        if len(sess.messages) > self.max_turns * 2:
            sess.messages = sess.messages[-(self.max_turns * 2):]

    def sanitize_and_bound_history(
        self,
        history: list[ChatMessage],
    ) -> list[ChatMessage]:
        """
        Sanitizes and bounds client-provided or stored conversation history:
        - Keeps at most max_turns (pairs of messages).
        - Truncates oldest messages if cumulative characters exceed max_history_chars.
        """
        if not history:
            return []

        # Keep last N turns
        recent = history[-(self.max_turns * 2):]

        # Check total character length
        bounded: list[ChatMessage] = []
        cumulative_len = 0

        # Traverse backwards to prioritize most recent messages
        for msg in reversed(recent):
            msg_len = len(msg.content)
            if cumulative_len + msg_len > self.max_history_chars and bounded:
                break
            bounded.insert(0, msg)
            cumulative_len += msg_len

        return bounded

    def contextualize_query(
        self,
        question: str,
        history: list[ChatMessage],
    ) -> str:
        """
        Resolves anaphoric/follow-up queries by incorporating salient keywords
        from the preceding conversation turn.
        Example:
            Q1: "Where is authenticate_user defined?"
            Q2: "What parameters does it take?" -> Augmented: "authenticate_user What parameters does it take?"
        """
        q_strip = question.strip()
        if not history or not q_strip:
            return q_strip

        # Check if question appears anaphoric or very brief (< 25 chars)
        is_anaphoric = any(p.search(q_strip) for p in self.ANAPHORIC_PATTERNS) or len(q_strip) < 25
        if not is_anaphoric:
            return q_strip

        # Find code symbols or key nouns in the previous user question
        prior_user_msgs = [m.content for m in history if m.role == "user"]
        if not prior_user_msgs:
            return q_strip

        last_user = prior_user_msgs[-1]
        # Extract candidate identifiers (camelCase, snake_case, or words >= 4 chars)
        identifiers = re.findall(r"\b[A-Za-z0-9_]{3,}\b", last_user)
        # Filter common English stopwords
        stopwords = {
            "where", "what", "when", "which", "how", "why", "does", "define", "defined",
            "show", "tell", "find", "this", "that", "from", "with", "user", "file", "code",
            "handler", "located", "inside", "about", "can", "you", "please",
        }
        salient = [ident for ident in identifiers if ident.lower() not in stopwords]

        # Prioritize true code identifiers (snake_case or camelCase)
        code_identifiers = [
            s for s in salient
            if "_" in s or any(c.isupper() for c in s[1:])
        ]

        if code_identifiers:
            anchor = code_identifiers[-1]
        elif salient:
            # Pick longest salient term
            anchor = max(salient, key=len)
        else:
            return q_strip

        if anchor.lower() not in q_strip.lower():
            return f"{anchor} {q_strip}"

        return q_strip

    def clear_session(self, session_id: str) -> None:
        """Clears memory state for a session."""
        self._sessions.pop(session_id, None)
