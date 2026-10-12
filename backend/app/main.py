"""
DevMind AI — FastAPI RAG Service
Entrypoint, middleware configuration, and health check.
Ref: PRD v1.2 Sections 7, 8; Step 5 of Antigravity Guide.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import get_settings
from .api.routes_ingest import router as ingest_router
from .api.routes_chat import router as chat_router
from .api.routes_auth import router as auth_router
from .api.routes_repositories import router as repositories_router

settings = get_settings()



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure storage directories are ready
    settings.ensure_storage_dirs()
    # Enforce 7-day retention policy cleanup on startup (PRD Section 17.10)
    from .services.ingestion.repository_manager import repo_manager
    repo_manager.cleanup_expired_repositories(settings.limits.retention_days)
    yield
    # Shutdown cleanup if any


app = FastAPI(
    title="DevMind AI Backend",
    version="1.2.0",
    description="Smart Codebase Assistant RAG service providing evidence-grounded answers.",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest_router)
app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(repositories_router)



@app.get("/")
def root():
    return {
        "message": "DevMind AI Backend is running.",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
def health_check():
    settings.ensure_storage_dirs()
    storage_ready = (
        settings.data_dir.exists()
        and settings.temp_storage_dir.exists()
        and settings.indices_dir.exists()
    )
    llm_valid, llm_message = settings.validate_llm_configuration()

    return {
        "status": "healthy" if storage_ready else "degraded",
        "service": "DevMind AI RAG Backend",
        "version": "1.2.0",
        "storage_ready": storage_ready,
        "llm_provider": settings.llm_provider,
        "llm_valid": llm_valid,
        "llm_message": llm_message,
        "limits": {
            "max_zip_mb": settings.limits.max_zip_mb,
            "max_files": settings.limits.max_files,
            "max_file_kb": settings.limits.max_file_kb,
            "retention_days": settings.limits.retention_days,
        },
    }
