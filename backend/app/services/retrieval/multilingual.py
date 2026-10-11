"""
Multilingual query processing and language adaptation for DevMind AI.
Ref: Step 30 of execution guide; PRD Section 6 (FR-07, FR-08).
Supports English, Hindi (Devanagari), and Hinglish (Romanized Hindi) developer queries:
- Detects query language/style.
- Extracts code identifiers, paths, and technical keywords.
- Generates retrieval query variants by augmenting Hindi/Hinglish programming intents with English search tokens.
- Preserves exact code identifiers, filenames, paths, and citation formats.
"""
from typing import Literal
import re

QueryLanguage = Literal["english", "hinglish", "hindi"]

DEVANAGARI_REGEX = re.compile(r"[\u0900-\u097F]")

# Common romanized Hindi particles/stop-words for Hinglish detection
HINGLISH_MARKERS = {
    "kaise", "kaunsi", "kaha", "kahan", "karta", "karti", "karte", "karen",
    "hota", "hoti", "hote", "hai", "hain", "kya", "kyun", "kis", "kisko",
    "baare", "bare", "me", "mein", "par", "pe", "se", "ko", "ke", "ki", "ka",
    "bhi", "aur", "ye", "yeh", "wo", "woh", "wala", "wali", "wale", "karo",
    "batao", "samjhao", "dikhaye", "chalega", "chalta", "chalti", "raha",
    "rahi", "rahe", "hoga", "hogi", "hoge", "bana", "banaya", "likha",
}

# Technical programming concepts mapped from Hindi/Hinglish to English search tokens
MULTILINGUAL_INTENT_MAP = {
    # Devanagari Hindi
    "प्रमाणीकरण": "authentication auth login",
    "लॉगिन": "login auth session",
    "रूटिंग": "routing route router endpoint",
    "रूट": "route routing endpoint",
    "डेटाबेस": "database db connection store",
    "डेटा": "data model schema entity",
    "मॉडल": "model schema entity",
    "कॉन्फ़िगरेशन": "config configuration settings env",
    "संरचना": "architecture structure layout",
    "प्रवेश": "entrypoint main app index",
    "त्रुटि": "error exception catch handler",
    "परीक्षण": "test testing spec",
    "सुरक्षा": "security guard auth permission",
    "फ़ाइल": "file",
    "फाइल": "file",
    "कार्य": "function method logic",
    "घटक": "component module",
    # Hinglish / Romanized Hindi
    "pramanikaran": "authentication auth login",
    "sandarbh": "reference citation",
    "jankari": "information details",
    "suraksha": "security auth guard",
    "rachna": "architecture structure",
    "kaha": "where location defined file",
    "kahan": "where location defined file",
    "kaise": "how implementation workflow",
    "kis": "which file location",
    "kaunsi": "which file component",
}


def is_hindi_query(query: str) -> bool:
    """Returns True if the query contains Devanagari script characters."""
    return bool(DEVANAGARI_REGEX.search(query))


def is_hinglish_query(query: str) -> bool:
    """Returns True if the query uses Latin script but contains conversational Hindi markers."""
    if is_hindi_query(query):
        return False

    tokens = re.findall(r"\b[A-Za-z]+\b", query.lower())
    if not tokens:
        return False

    matches = sum(1 for t in tokens if t in HINGLISH_MARKERS)
    # If 2 or more distinct Hinglish markers, or > 20% of words are Hinglish markers
    return matches >= 2 or (len(tokens) > 2 and (matches / len(tokens)) >= 0.25)


def detect_language(query: str) -> QueryLanguage:
    """
    Detects the user query's linguistic category:
    - 'hindi': Query contains Devanagari script.
    - 'hinglish': Query uses Latin script with conversational Hindi markers.
    - 'english': Default English or technical query.
    """
    if is_hindi_query(query):
        return "hindi"
    if is_hinglish_query(query):
        return "hinglish"
    return "english"


def extract_code_tokens(query: str) -> list[str]:
    """
    Extracts code identifiers, technical terms, camelCase, snake_case,
    and file paths embedded within the query text.
    """
    # File paths (e.g. src/app/auth.ts, route.ts, app.py)
    path_matches = re.findall(r"[A-Za-z0-9_\-\./\\]+\.[A-Za-z0-9]+", query)

    # Identifiers (camelCase, PascalCase, snake_case)
    id_matches = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*[A-Z0-9_][a-zA-Z0-9_]*\b", query)

    # Common technical programming keywords in Latin script
    tech_keywords = {
        "auth", "login", "jwt", "session", "user", "token", "password",
        "route", "router", "endpoint", "api", "controller", "handler",
        "database", "db", "model", "schema", "entity", "table", "column",
        "config", "settings", "env", "environment", "port", "host",
        "main", "app", "index", "entry", "start", "bootstrap",
        "middleware", "guard", "security", "permission", "role",
        "test", "testing", "spec", "mock", "stub",
        "error", "exception", "validation", "request", "response",
        "component", "hook", "state", "props", "layout", "page",
    }

    words = re.findall(r"\b[A-Za-z]{3,}\b", query.lower())
    found_tech = [w for w in words if w in tech_keywords]

    combined = list(dict.fromkeys(path_matches + id_matches + found_tech))
    return combined


def expand_multilingual_query(query: str) -> str:
    """
    Produces an augmented search query variant for hybrid retrieval.
    If query is Hinglish or Hindi:
    - Preserves all original query text (for multilingual embedding semantic search).
    - Appends extracted English code identifiers and mapped technical search tokens
      to ensure Okapi BM25 scores English codebase files accurately.
    """
    q_clean = query.strip()
    if not q_clean:
        return q_clean

    lang = detect_language(q_clean)
    if lang == "english":
        return q_clean

    additional_tokens: list[str] = []

    # 1. Add extracted code tokens / paths / identifiers
    code_tokens = extract_code_tokens(q_clean)
    additional_tokens.extend(code_tokens)

    # 2. Check Hindi/Hinglish intent maps
    q_lower = q_clean.lower()
    for term, expansion in MULTILINGUAL_INTENT_MAP.items():
        if term in q_lower:
            for exp_token in expansion.split():
                if exp_token not in additional_tokens:
                    additional_tokens.append(exp_token)

    if not additional_tokens:
        return q_clean

    # Append distinct expansion tokens to base query
    expansion_str = " ".join(additional_tokens)
    return f"{q_clean} {expansion_str}"
