# AI Smart Notes — Project Status & Roadmap

_Last updated: 2026-07-14_ · Phases 1–4 complete; Phase 5 (frontend/voice/deploy) next.

A single-page map of **what is built** and **what is planned**, across all five
phases. Legend: ✅ done · 🔨 in progress · ⬜ planned.

---

## Phase overview

| Phase | Theme | Status |
|-------|-------|--------|
| **1** | Notes & Tasks CRUD (FastAPI + PostgreSQL) | ✅ Complete |
| **2** | AI categorization + priority detection (OpenRouter) | ✅ Complete |
| **3** | Embeddings + semantic search (sentence-transformers + ChromaDB) | ✅ Complete |
| **4** | Chat with notes (RAG pipeline) | ✅ Complete |
| **5** | React frontend, image attachments, Docker deployment | 🔵 In progress |

---

## What the app does (and will do)

- **Now:** Create/read/update/delete notes and tasks. Every note is
  automatically tagged with a **category** (Work, Coding, Health, …) and a
  **priority** (High/Medium/Low) by an LLM via OpenRouter.
- **Being added (Phase 3):** Search notes by **meaning**, not keywords — e.g.
  searching "learn backend" finds a note about "study FastAPI and SQLAlchemy",
  ranked by a similarity percentage.
- **Later:** Ask questions and chat with your notes (RAG), then a web UI with
  voice input, and production deployment.

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

Local embeddings (**sentence-transformers**, `all-MiniLM-L6-v2`) + local vector DB
(**ChromaDB**, persisted to disk). Vectors live in Chroma, **never** in Postgres.
Postgres stays the source of truth; the vector index is best-effort, so if Chroma
is down, CRUD is unaffected.

### Build order & status

| # | File | Purpose | Status |
|---|------|---------|--------|
| 1 | `requirements.txt` | + `sentence-transformers`, `chromadb` | ✅ |
| 2 | `app/core/config.py` | + embedding/Chroma settings (`.env`, `.env.example`) | ✅ |
| 3 | `app/ai/embedding_models.py` | DTOs: `VectorMetadata`, `SearchResult` | ✅ |
| 4 | `app/ai/embedding_service.py` | sentence-transformers wrapper (text → vector) | ✅ |
| 5 | `app/vectordb/chroma_client.py` | Persistent Chroma client + collection (cosine) | ✅ |
| 6 | `app/vectordb/vector_store.py` | `upsert` / `delete` / `query` on the collection | ✅ |
| 7 | `app/vectordb/search.py` | Query → embed → search → ranked `SearchResult`s | ✅ |
| 8 | `app/services/note_embedding_service.py` | Write-side bridge; never raises (Feature 7) | ✅ |
| 9 | `app/services/note_service.py` | Hook sync into create/update/delete | ✅ |
| 10 | `app/api/routes/search.py` | `GET /search?query=...` | ✅ |
| 11 | `app/main.py` | Register the search router | ✅ |
| 12 | `README.md` | Phase 3 docs, diagrams, examples, scaling notes | ✅ |

Phase 3 is complete: `main.py` mounts the search router at `GET /api/v1/search`,
`note_service` syncs the vector index on note create / update / delete
(best-effort — a Chroma failure never breaks CRUD), and `README.md` documents
the endpoint, the write/query flow, setup, and scaling notes. **Next up: Phase 4
(chat with notes / RAG).**

### How it will fit together

```
WRITE (on note create/update/delete)
  note_service ──► note_embedding_service ──► embedding_service (text→vector)
                                         └──► vector_store ──► chroma_client ──► ChromaDB (disk)

QUERY (GET /search)
  search router ──► search.py ──► embedding_service (query→vector)
                              └──► vector_store ──► ChromaDB ──► ranked SearchResults (with similarity %)
```

- **Sync (Feature 5):** vector id = `str(note_id)` → update = upsert, delete = delete.
- **Metadata (Feature 2):** note_id, title, category, priority, created_at, updated_at stored on each vector and returned with results.
- **Score (Feature 4):** cosine distance → `similarity_score` percentage, sorted high→low.

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

## Phase 5 — Frontend, images, deployment 🔵 In progress

- **React frontend** consuming the API ✅ — Vite + React 19 + TypeScript + Tailwind v4;
  Notes / Tasks / Search / Chat tabs in `frontend/`.
- **Image attachments** ✅ — notes can carry multiple images (one-to-many
  `note_images` table, migration `0003`). Bytes stored on local disk under
  `./media`, served via a FastAPI `/media` static mount; upload/list/delete
  endpoints at `/api/v1/notes/{id}/images`; thumbnail grid + upload UI in the
  Notes view. Verified end-to-end.
- **Deployment** ✅ — Docker Compose: `api` (FastAPI) + `web` (nginx serving the
  built SPA and reverse-proxying `/api` + `/media`). Two named volumes persist
  `chroma_data` and `media`; Postgres stays remote (Neon). See the README
  "Deployment (Docker)" section. `docker compose up --build`.
- **Voice notes** — dropped (Web Speech API was unreliable in-browser; feature
  and its files were removed).
- **Production optimization** (caching, batching, scaling the vector store) —
  still open.

---

## How to run what exists today

```bash
python -m venv .venv && .\.venv\Scripts\Activate.ps1     # Windows
pip install -r requirements.txt
copy .env.example .env        # set DATABASE_URL + OPENROUTER_API_KEY
createdb ai_smart_notes
alembic upgrade head          # applies 0001 + 0002
uvicorn app.main:app --reload # docs at http://127.0.0.1:8000/docs
```

> Phase 3 & 4 are wired in: `GET /api/v1/search?query=...` (semantic search) and
> `POST /api/v1/chat` (chat with notes / RAG) are live, and notes are indexed
> into ChromaDB on create/update/delete.
> All code so far is syntax-verified (`py_compile`); it has not been run
> against a live PostgreSQL / OpenRouter / Chroma in this workspace.

---

## Working agreement

Build **one file at a time**: explain why the file exists → write it → explain
the flow → **stop and wait for confirmation**. Existing CRUD architecture is not
rewritten; new features are added at clean seams (services / new packages).
