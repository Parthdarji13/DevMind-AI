# DevMind AI — Smart Codebase Assistant

> Evidence-grounded codebase intelligence powered by hybrid RAG with verified, inspectable line citations.

DevMind AI enables engineering teams to understand, explore, and query medium-to-large software repositories (5,000 to 10,000+ lines of code) through an intuitive chat workspace. Every factual answer is strictly anchored in actual source code and accompanied by exact, verified citations `[File: <path>, Lines: <start>-<end>]`. If evidence is absent, DevMind AI abstains rather than halluncinating code.

---

## Key Features

- **Multi-Source Ingestion**: Upload local source ZIP archives (up to 100 MB) or provide public Git HTTPS repository URLs with automated shallow cloning and SSRF protection.
- **Zero-Execution Code Sandbox**: Ingested repository files are analyzed purely statically. Code, scripts, and binaries are never executed, compiled, or evaluated.
- **Automated Filtering & Secret Exclusion**: Automatically filters `node_modules/`, lockfiles, build artifacts (`dist/`, `.next/`), binaries, and sensitive credential files (`.env`, `*.pem`, `id_rsa`, `*.key`).
- **Syntax-Aware AST Chunking**: Chunks code along function and class boundaries while preserving deterministic 1-indexed start and end line ranges.
- **Hybrid Retrieval (BM25 + Dense Vectors)**: Merges exact keyword/symbol matches via Okapi BM25 and semantic embeddings via dense vector search using Reciprocal Rank Fusion (RRF).
- **Strict Citation Validation**: Post-processes model responses with regex verification to guarantee every cited file and line range exists in the retrieved evidence set.
- **Multilingual Support (English, Hinglish & Hindi)**: Query naturally in English, Romanized Hinglish, or Devanagari Hindi with automatic BM25 technical token expansion while preserving all code identifiers and citations in verbatim English.
- **Interactive Evidence Drawer**: Click inline citation chips to inspect full code snippets, line numbers, and file context in a slide-out modal.
- **Repository-Derived Suggested Questions**: Automatically extracts entry points, routers, models, and architecture questions based on actual indexed file paths and symbols.

---

## Architecture Overview

```
                         ┌───────────────────────────────────────┐
                         │       Next.js 16 Frontend (UI)        │
                         │   Upload • Indexing • Chat Workspace   │
                         └──────────────────┬────────────────────┘
                                            │ HTTP / JSON
                                            ▼
                         ┌───────────────────────────────────────┐
                         │         FastAPI Backend Engine        │
                         └──────────────────┬────────────────────┘
                                            │
         ┌──────────────────────────────────┴──────────────────────────────────┐
         ▼                                                                     ▼
┌─────────────────────────────────┐                         ┌──────────────────────────────────┐
│        Ingestion Pipeline       │                         │       Hybrid Retrieval & QA      │
├─────────────────────────────────┤                         ├──────────────────────────────────┤
│ 1. ZIP / Git Ingestion          │                         │ 1. Multilingual Query Expansion  │
│ 2. SSRF & Path Traversal Guards │                         │ 2. Okapi BM25 Lexical Search     │
│ 3. Secret & Artifact Filtering  │                         │ 3. Dense Vector Cosine Sim       │
│ 4. AST Symbol-Aware Chunking    │                         │ 4. Reciprocal Rank Fusion (RRF)  │
│ 5. Persistent Local Storage     │                         │ 5. Grounded Prompt Contract      │
│    (./data/indices/{repo_id})   │                         │ 6. Strict Citation Verification  │
└─────────────────────────────────┘                         └──────────────────────────────────┘
```

---

## Prerequisites

- **Python**: 3.11+ (Python 3.12 recommended)
- **Node.js**: 18.17+ or 20+ (Node.js 22 verified)
- **npm**: 9+ or 10+
- **Git**: 2.30+ installed and available in `PATH`

---

## Quickstart & Setup

### 1. Clone the Repository

```bash
git clone <repository_url>
cd "DevMind AI"
```

### 2. Configure Environment Variables

Copy the provided template to `.env`:

```bash
cp .env.example .env
```

Open `.env` and set your preferred LLM provider key:

```env
# LLM Provider ("google_genai" | "openai" | "groq" | "mock")
LLM_PROVIDER=google_genai
LLM_MODEL=gemini-flash-latest
GEMINI_API_KEY=your_gemini_api_key_here


# Embedding Provider ("local" | "google_genai" | "openai")
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

> **Note**: For testing without external API keys, you can set `LLM_PROVIDER=mock` and `EMBEDDING_PROVIDER=local`.

### 3. Backend Setup & Startup

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv

# On Windows:
.\.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server on port 8000
uvicorn app.main:app --reload --port 8000
```

The backend health check endpoint will be available at [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health).

### 4. Frontend Setup & Startup

In a separate terminal:

```bash
cd frontend

# Install dependencies
npm install

# Start Next.js development server on port 3000
npm run dev
```

Open your browser at [http://localhost:3000](http://localhost:3000) to access the DevMind AI workspace.

---

## Running Test Suites

DevMind AI includes 133 automated unit, integration, and end-to-end tests:

### Backend Test Suite (Pytest)

```bash
# Run full backend test suite (from project root)
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/ -v

# Run specific end-to-end flow tests
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_end_to_end_flows.py -v

# Run multilingual QA tests
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_multilingual_qa.py -v
```

### Large Repository Scale Benchmark (5,000 - 10,000+ LOC)

```bash
.\backend\.venv\Scripts\python.exe backend/scripts/benchmark_large_repo.py
```

### Frontend Build & Lint Verification

```bash
cd frontend

# Run ESLint
npx eslint .

# Run production build (Next.js 16 with Turbopack)
npm run build
```

---

## Repository Limits & Guardrails

| Parameter | Limit | Behavior when Exceeded |
|---|---|---|
| Maximum Archive Upload | 100 MB | Clean 400 Bad Request with explicit limit message |
| Maximum File Count | 3,000 files | Files beyond capacity are pruned with breakdown reported |
| Maximum File Size | 1,000 KB (1 MB) | Skipped with `oversized` category recorded |
| Ingestion Timeout | 60 seconds | Aborts clone with clean 504 Gateway Timeout error |
| Local Retention Window | 7 days | Index metadata retained; cleaned automatically or on reset |
| Query Length | 2,000 characters | Returns HTTP 422 Unprocessable Content |

---

## Security & Privacy Policies

1. **Zero Untrusted Code Execution**: Uploaded source code is never executed, imported into the runtime, or built. Analysis is strictly static (tokenization, regex, AST).
2. **Local Repository Isolation**: Each repository is indexed into its own isolated directory (`./data/indices/{repo_id}`). Cross-tenant data bleed is impossible.
3. **Zip-Slip & Symlink Defense**: Zip entry extraction enforces strict path confinement, rejecting `../`, `..\\`, Windows drive letters (`C:`), and Unix symlinks.
4. **SSRF Guardrails**: Git URL ingestion only permits public `https://` endpoints. Private IP ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, and AWS IMDS `169.254.169.254`) are blocked prior to connection.
5. **Secret Redaction**: Files matching credential signatures (`.env`, `*.pem`, `id_rsa`, `*.key`) are excluded from ingestion.
6. **External LLM Disclosure**: When asking questions, only the top retrieved relevant code snippets are transmitted to your configured LLM provider to synthesize grounded answers. Raw repository archives remain on your local machine.

---

## Troubleshooting

### 1. Port Conflicts (8000 or 3000 in use)
If port 8000 is occupied:
```bash
uvicorn app.main:app --port 8001
```
Then update `NEXT_PUBLIC_API_URL=http://localhost:8001` in your frontend environment.

### 2. Vector Dimension Mismatch
If switching embedding models (e.g. from local 384-dim to an external provider):
Clear the existing index cache in `./data/indices/` or click **"Switch Repository"** in the chat sidebar to re-index with the new model.

### 3. LLM Rate Limit (429) or Gateway Timeout (504)
If your external LLM provider encounters rate limits:
- The UI displays an inline retry notification with cooldown advice.
- You can switch to another provider in `.env` (e.g. Google Gemini 2.0 Flash has generous rate limits) or use `LLM_PROVIDER=mock` for testing.

---

## License

This project is licensed under the Apache 2.0 License.
