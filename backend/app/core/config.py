"""
Application configuration for DevMind AI.
Provides safe environment defaults, type conversion, and error reporting.
"""
from dataclasses import dataclass, field
from pathlib import Path
import os

try:
    from dotenv import load_dotenv
    # Load .env from root workspace or backend folder if present
    _root_env = Path(__file__).resolve().parent.parent.parent.parent / ".env"
    _backend_env = Path(__file__).resolve().parent.parent.parent / ".env"
    if _root_env.exists():
        load_dotenv(_root_env)
    elif _backend_env.exists():
        load_dotenv(_backend_env)
    else:
        load_dotenv()
except ImportError:
    pass

from .limits import IngestionLimits, DEFAULT_LIMITS


@dataclass
class Settings:
    # Server settings
    host: str = field(default_factory=lambda: os.getenv("FASTAPI_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("FASTAPI_PORT", "8000")))
    cors_origins: list[str] = field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
            if origin.strip()
        ]
    )

    # Directories
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent.parent)
    data_dir: Path = field(
        default_factory=lambda: Path(os.getenv("DATA_DIR", "./data")).resolve()
    )
    temp_storage_dir: Path = field(
        default_factory=lambda: Path(os.getenv("TEMP_STORAGE_DIR", "./data/temp_repos")).resolve()
    )
    indices_dir: Path = field(
        default_factory=lambda: Path(os.getenv("INDICES_DIR", "./data/indices")).resolve()
    )

    # Limits
    limits: IngestionLimits = field(default_factory=IngestionLimits)

    # LLM Settings
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "google_genai").lower())
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gemini-2.0-flash"))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))

    # Embedding Settings
    embedding_provider: str = field(default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "local").lower())
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))

    def validate_llm_configuration(self) -> tuple[bool, str]:
        """Validates that credentials exist for active LLM provider, or returns informative error."""
        if self.llm_provider == "mock":
            return True, "Mock provider active (offline mode)"
        if self.llm_provider == "google_genai":
            if not self.gemini_api_key or self.gemini_api_key.startswith("your_"):
                return False, "GEMINI_API_KEY is not configured or contains placeholder value."
            return True, "Google GenAI configured"
        if self.llm_provider == "openai":
            if not self.openai_api_key or self.openai_api_key.startswith("your_"):
                return False, "OPENAI_API_KEY is not configured or contains placeholder value."
            return True, "OpenAI configured"
        if self.llm_provider == "groq":
            if not self.groq_api_key or self.groq_api_key.startswith("your_"):
                return False, "GROQ_API_KEY is not configured or contains placeholder value."
            return True, "Groq configured"
        return False, f"Unsupported LLM provider: {self.llm_provider}"

    def ensure_storage_dirs(self) -> None:
        """Ensures required local runtime directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.temp_storage_dir.mkdir(parents=True, exist_ok=True)
        self.indices_dir.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings()
