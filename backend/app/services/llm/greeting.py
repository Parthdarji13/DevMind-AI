"""
Greeting detection and personalized greeting response generator for DevMind AI.
Greets users by their name or ID in both text chat and voice.
"""
import re
from typing import Optional

# Regex for pure greetings like "hi", "hello", "hii", "hey devmind", "namaste", "good morning"
PURE_GREETING_PATTERN = re.compile(
    r"^(?:h[ie]+y*|hello+|hey+|namaste|hola|good\s+(?:morning|afternoon|evening)|kaise\s+ho|kya\s+haal\s+hai)"
    r"(?:\s+(?:there|devmind|ai))?[\s!.,?]*$",
    re.IGNORECASE,
)

# Regex for greeting prefix like "hi devmind, what is this project?"
PREFIX_GREETING_PATTERN = re.compile(
    r"^(?:h[ie]+y*|hello+|hey+|namaste|good\s+(?:morning|afternoon|evening))"
    r"(?:\s+(?:there|devmind|ai))?[\s!.,]+(.*)$",
    re.IGNORECASE,
)

HINGLISH_GREETING_WORDS = {"kaise", "haal", "namaste", "kya", "aap"}


def is_hinglish_greeting(query: str) -> bool:
    """Checks if the greeting contains Hindi/Hinglish phrasing."""
    tokens = set(re.findall(r"\b[a-zA-Z]+\b", query.lower()))
    return bool(tokens.intersection(HINGLISH_GREETING_WORDS))


def extract_user_display_name(
    user_name: Optional[str] = None, user_id: Optional[str] = None, email: Optional[str] = None
) -> str:
    """Resolves a friendly display name for the user (e.g. 'Parth')."""
    if user_name and user_name.strip() and user_name.strip().lower() != "guest developer":
        # Extract first name and clean
        first = user_name.strip().split()[0]
        cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "", first)
        if cleaned:
            return cleaned.capitalize()

    if email and email.strip() and "@" in email:
        prefix = email.strip().split("@")[0]
        if prefix and prefix.lower() not in ("guest", "admin", "user"):
            cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "", prefix)
            if cleaned:
                return cleaned.capitalize()

    if user_id and user_id.strip() and user_id.strip().lower() != "guest_default":
        raw = user_id.strip()
        if "@" in raw:
            return raw.split("@")[0].capitalize()
        if not raw.startswith("usr_"):
            return raw.capitalize()

    return "Parth"  # Default developer name requested by user


def is_pure_greeting(query: str) -> bool:
    """Checks if the user's inquiry is solely a greeting."""
    q = query.strip()
    return bool(PURE_GREETING_PATTERN.match(q))


def extract_greeting_prefix(query: str) -> Optional[str]:
    """If the query starts with a greeting followed by an inquiry, returns the inquiry part."""
    q = query.strip()
    m = PREFIX_GREETING_PATTERN.match(q)
    if m:
        remaining = m.group(1).strip()
        if remaining and len(remaining) > 3:
            return remaining
    return None


def generate_greeting_response(display_name: str, is_voice: bool = False, is_hinglish: bool = False) -> str:
    """Generates a warm, personalized greeting for DevMind."""
    if is_voice:
        if is_hinglish:
            return f"Hii, {display_name}! Kaise hain aap? Main DevMind AI hoon. Is project ke baare me aap kya jaanana chahte hain?"
        return f"Hii, {display_name}! I am DevMind AI. How can I help you explore this project today?"
    else:
        if is_hinglish:
            return (
                f"Hii, {display_name}! 👋 Main DevMind AI hoon, aapka codebase assistant.\n\n"
                f"Aap mujhse is project ke architecture, API endpoints, authentication flows, ya kisi bhi code ke baare me pooch sakte hain!"
            )
        return (
            f"Hii, {display_name}! 👋 I am DevMind AI, your codebase assistant.\n\n"
            f"How can I help you explore this project today? You can ask me about the architecture, API routes, authentication flows, or code execution!"
        )
