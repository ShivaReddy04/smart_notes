# AI Smart Notes — Project Status & Roadmap

_Last updated: 2026-07-17_ · Phases 1–5 complete; reworked to deploy on Render's **free tier** (hosted Gemini embeddings + Postgres pgvector + Cloudflare R2, no torch, no disk).

A single-page map of **what is built** and **what is planned**, across all five
phases. Legend: ✅ done · 🔨 in progress · ⬜ planned.

---

## Phase overview

| Phase | Theme | Status |
|-------|-------|--------|
| **1** | Notes & Tasks CRUD (FastAPI + PostgreSQL) | ✅ Complete |
| **2** | AI categorization + priority detection (OpenRouter) | ✅ Complete |
| **3** | Embeddings + semantic search (**Gemini embeddings + Postgres pgvector**) | ✅ Complete |
| **4** | Chat with notes (RAG pipeline) | ✅ Complete |
| **5** | React frontend, image attachments (**Cloudflare R2**), **Render free-tier deploy** | ✅ Complete |

---

## What the app does (and will do)

- **CRUD:** Create/read/update/delete notes and tasks. Every note is
  automatically tagged with a **category** (Work, Coding, Health, …) and a
  **priority** (High/Medium/Low) by an LLM via OpenRouter.
- **Semantic search:** Find notes by **meaning**, not keywords — e.g. searching
  "learn backend" finds a note about "study FastAPI and SQLAlchemy", ranked by a
  similarity percentage (Gemini embeddings + pgvector).
- **Chat:** Ask questions and get answers grounded only in your notes (RAG).
- **Web UI + images:** A React SPA (Notes/Tasks/Search/Chat) with image
  attachments, deployable free on Render.

---

## Phase 1 — CRUD foundation ✅

Clean-architecture backend. Dependency rule: `routes → services → repositories → models`.

| File | Purpose | Status |
|------|---------|--------|
| `app/core/config.py` | Typed settings from `.env` | ✅ |
| `app/core/database.py` | Engine, session, `Base`, `get_db` | ✅ |
| `app/db/base.py` | Model registry for Alembic | ✅ |
| `app/models/note.py`, `task.py`, `mixins.py` | ORM tables + `TaskStatus`, timestamps | ✅ |
| `app/schemas/note.py`, `task.py` | Create/Update/Response validation | ✅ |
| `app/repositories/note_repository.py`, `task_repository.py` | All SQL | ✅ |
| `app/services/note_service.py`, `task_service.py` | Business logic | ✅ |
| `app/utils/exceptions.py` | Domain errors → HTTP mapping | ✅ |
| `app/api/routes/notes.py`, `tasks.py` | REST endpoints | ✅ |
| `app/main.py` | App assembly + error handlers | ✅ |
| `alembic/…/0001_initial_schema.py` | Creates notes + tasks tables | ✅ |

**Endpoints:** `POST/GET/PUT/DELETE /notes`, `PATCH /notes/{id}/pin`,
`POST/GET/PUT/DELETE /tasks`, `PATCH /tasks/{id}/status`, `GET /health`.

---

## Phase 2 — AI categorization & priority ✅

New `app/ai/` package; LLM via **OpenRouter** (OpenAI-compatible, model set in `.env`).

| File | Purpose | Status |
|------|---------|--------|
| `app/ai/schemas.py` | `Category`/`Priority` enums + `NoteAnalysis` (coercion + fallback) | ✅ |
| `app/ai/prompts.py` | Prompt text + `ChatPromptTemplate` builder | ✅ |
| `app/ai/llm.py` | `ChatOpenAI` factory → OpenRouter | ✅ |
| `app/ai/categorizer.py` | `prompt \| llm \| parser`; `analyze()` never raises | ✅ |
| `app/models/note.py` | + `category`, `priority` columns | ✅ |
| `app/schemas/note.py` | + `category`, `priority` on response (read-only) | ✅ |
| `app/services/note_service.py` | Runs AI on create/update | ✅ |
| `alembic/…/0002_add_note_ai_fields.py` | Adds the two columns | ✅ |

**Behavior:** create a note → response includes auto-assigned `category` + `priority`.
If the LLM fails: logged, falls back to `Other` / `Medium`, CRUD still succeeds.

---

## Phase 3 — Embeddings & semantic search ✅

**Hosted embeddings** (Google **Gemini** `text-embedding-004`, called via
`langchain-openai`'s `OpenAIEmbeddings` pointed at Gemini's OpenAI-compatible
endpoint) + **vectors stored in Postgres via `pgvector`** — same database as the
notes, no separate vector service and no disk. Postgres stays the source of
truth; the vector index is best-effort, so if the embeddings API or vector write
is down, CRUD is unaffected.

> **Originally** built with local sentence-transformers + ChromaDB-on-disk. That
> needed ~2 GB RAM (torch) and a persistent disk, neither of which fits a free
> tier — so Phase 3 was reworked to the hosted-Gemini + pgvector design above
> (2026-07-17). `chroma_client.py` was deleted.

### Build order & status

| # | File | Purpose | Status |
|---|------|---------|--------|
| 1 | `requirements.txt` | − `sentence-transformers`/`chromadb`, + `pgvector` | ✅ |
| 2 | `app/core/config.py` | Gemini embedding + dims settings (`.env`, `.env.example`) | ✅ |
| 3 | `app/ai/embedding_models.py` | DTOs: `VectorMetadata`, `SearchResult` | ✅ |
| 4 | `app/ai/embedding_service.py` | Hosted embeddings client (text → vector) | ✅ |
| 5 | `app/models/note_embedding.py` | `NoteEmbedding` ORM: note_id + `Vector(768)` | ✅ |
| 6 | `alembic/…/0004_add_note_embeddings.py` | `CREATE EXTENSION vector` + table + HNSW index | ✅ |
| 7 | `app/vectordb/vector_store.py` | `upsert` / `delete` / `query` in pgvector (own session) | ✅ |
| 8 | `app/vectordb/search.py` | Query → embed → search → ranked `SearchResult`s | ✅ |
| 9 | `app/services/note_embedding_service.py` | Write-side bridge; never raises (Feature 7) | ✅ |
| 10 | `app/services/note_service.py` | Hook sync into create/update/delete | ✅ |
| 11 | `app/api/routes/search.py` | `GET /search?query=...` | ✅ |
| 12 | `app/main.py` | Register the search router | ✅ |
| 13 | `README.md` | Phase 3 docs, diagrams, examples, scaling notes | ✅ |

### How it fits together

```
WRITE (on note create/update/delete)
  note_service ──► note_embedding_service ──► embedding_service (text→vector, Gemini)
                                         └──► vector_store ──► note_embeddings (pgvector)

QUERY (GET /search)
  search router ──► search.py ──► embedding_service (query→vector, Gemini)
                              └──► vector_store ──► pgvector `<=>` + JOIN notes ──► ranked results
```

- **Sync (Feature 5):** vector row keyed on `note_id` → update = upsert, delete = delete.
- **Metadata (Feature 2):** the vector row holds only the embedding; note_id, title, category, priority, and timestamps come from a JOIN to `notes`, so hits reflect the note's current state.
- **Score (Feature 4):** cosine distance (`<=>`) → `similarity_score` percentage, sorted high→low.

---

## Phase 4 — Chat with notes (RAG) ✅

Retrieval-augmented generation: answer a question using the user's own notes as
grounding. Reuses Phase 3 retrieval (`SearchService`) and Phase 2 generation
(`get_llm()` → OpenRouter) — a thin RAG layer, no rewrite of existing code and
no new migration or config.

### Build order & status

| # | File | Purpose | Status |
|---|------|---------|--------|
| 1 | `app/schemas/chat.py` | `ChatRequest` / `ChatSource` / `ChatResponse` contracts | ✅ |
| 2 | `app/ai/rag_prompts.py` | Grounded RAG prompt (answer only from retrieved notes) | ✅ |
| 3 | `app/ai/rag.py` | `RAGService.ask()`: retrieve → build context → generate | ✅ |
| 4 | `app/api/routes/chat.py` | `POST /chat` endpoint | ✅ |
| 5 | `app/main.py` | Register the chat router | ✅ |
| 6 | `README.md` | Phase 4 docs, diagram, examples | ✅ |

### How it fits together

```
POST /chat ──► chat router ──► RAGService.ask()
                                 ├─► SearchService  (retrieve ranked notes)   [Phase 3]
                                 ├─► rag_prompts     (grounded context prompt)
                                 └─► get_llm() → StrOutputParser (answer)      [Phase 2]
                                 ◄─ ChatResponse { answer, sources }
```

- **Grounded:** the prompt forbids outside knowledge; the model answers only
  from the retrieved notes or admits it can't.
- **Sources returned:** each answer carries the notes it was built from
  (id, title, similarity %), so answers are verifiable.
- **Empty retrieval is graceful:** no relevant notes → honest "nothing found"
  answer, empty sources, no LLM call.
- **Failures surface:** a generation error is a 500 (via main.py's catch-all),
  never a fabricated answer — the opposite of the categorizer's safe-fallback
  policy, matching search's "never disguise a failure" stance.
- **Bounded context:** notes are packed into the prompt up to `MAX_CONTEXT_CHARS`
  (a module constant), dropping least-relevant notes first.

---

## Phase 5 — Frontend, images, deployment ✅

- **React frontend** consuming the API ✅ — Vite + React 19 + TypeScript + Tailwind v4;
  Notes / Tasks / Search / Chat tabs in `frontend/`.
- **Image attachments** ✅ — notes can carry multiple images (one-to-many
  `note_images` table, migration `0003`). Storage is pluggable via
  `IMAGE_STORAGE_BACKEND`: **local disk** (dev) or **Cloudflare R2** (production,
  S3 API via boto3) — `image_storage_service.py` is an abstract base with
  `LocalImageStorage` / `R2ImageStorage`. The response `url` is an absolute R2
  URL under `r2`, or a `/media/...` path under `local`; upload/list/delete
  endpoints at `/api/v1/notes/{id}/images`; thumbnail grid + upload UI in Notes.
- **Deployment** ✅ — **Render free tier** via `render.yaml` Blueprint: a Docker
  `api` service (`plan: free`, no disk) + a static `web` service. No torch (fits
  512 MB RAM), vectors in pgvector, images in R2 — nothing needs a paid disk.
  `docker-compose.yml` still runs the full stack locally (single `media` volume).
- **Voice notes** — dropped (Web Speech API was unreliable in-browser; feature
  and its files were removed).

### Free-deploy rework (2026-07-17)

The stack was reworked from "runs on a paid box" to "runs free on Render":

| Concern | Before | After |
|---------|--------|-------|
| Embeddings | local sentence-transformers (torch, ~2 GB RAM) | hosted **Gemini** API (no torch) |
| Vectors | ChromaDB on a persistent disk | **pgvector** in Neon Postgres |
| Image bytes | local disk (`./media`) | **Cloudflare R2** (S3-compatible) |
| Render plan | `standard` (~$25/mo) + 5 GB disk | `free`, no disk |

Files touched: `requirements.txt`, `config.py`, `embedding_service.py`,
`vector_store.py`, `note_embedding_service.py`, new `note_embedding.py` +
migration `0004`, deleted `chroma_client.py`, `image_storage_service.py`,
`note_image.py` schema, `main.py`, frontend `client.ts`, `Dockerfile`,
`render.yaml`, `docker-compose.yml`, `.env`/`.env.example`.

- **Still open:** background/queued embedding for high write volume, caching,
  and batching of embedding calls.

---

## How to run what exists today

```bash
python -m venv .venv && .\.venv\Scripts\Activate.ps1     # Windows
pip install -r requirements.txt
copy .env.example .env        # set DATABASE_URL + OPENROUTER_API_KEY + EMBEDDING_API_KEY
alembic upgrade head          # applies 0001–0004 (incl. CREATE EXTENSION vector)
uvicorn app.main:app --reload # docs at http://127.0.0.1:8000/docs
```

> `DATABASE_URL` must point at a **pgvector-capable Postgres** (e.g. Neon).
> `GET /api/v1/search` (semantic search) and `POST /api/v1/chat` (RAG) are live;
> notes are embedded (Gemini) and indexed into the `note_embeddings` pgvector
> table on create/update/delete. To deploy free, see the README
> "Deployment — Render (free tier)" section (`render.yaml` Blueprint).

---

## Working agreement

Build **one file at a time**: explain why the file exists → write it → explain
the flow → **stop and wait for confirmation**. Existing CRUD architecture is not
rewritten; new features are added at clean seams (services / new packages).
