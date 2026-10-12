"""
Application configuration for DevMind AI.
Provides safe environment defaults, type conversion, and error reporting.
"""
from dataclasses import dataclass, field
from pathlib import Path
import os

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def reload_env() -> None:
    """Reloads environment variables from root and backend .env files dynamically."""
    if not load_dotenv:
        return
    try:
        core_dir = Path(__file__).resolve().parent
        root_env = (core_dir / ".." / ".." / ".." / ".env").resolve()
        backend_env = (core_dir / ".." / ".." / ".env").resolve()

        if root_env.exists():
            load_dotenv(root_env, override=True)
        if backend_env.exists():
            if not os.getenv("GEMINI_API_KEY"):
                load_dotenv(backend_env, override=True)
            else:
                load_dotenv(backend_env, override=False)
    except Exception:
        pass


# Initial load
reload_env()

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
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gemini-flash-latest"))
    llm_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT_SECONDS", "60.0")))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))

    # Embedding Settings
    embedding_provider: str = field(default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "local").lower())
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))

    # Auth Settings
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", "devmind_ai_super_secret_jwt_key_2026"))
    google_client_id: str = field(default_factory=lambda: os.getenv("GOOGLE_CLIENT_ID", ""))


    def validate_llm_configuration(self) -> tuple[bool, str]:
        """Validates that credentials exist for active LLM provider, or returns informative error."""
        if self.llm_provider == "mock":
            return True, "Mock provider active (offline mode)"
        if self.llm_provider in ("google_genai", "google", "gemini"):
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
    reload_env()
    return Settings()
