# AI Smart Notes — Backend

A production-structured FastAPI + PostgreSQL backend for notes and tasks,
built with Clean Architecture. Beyond CRUD, every note is automatically
**categorized and prioritized** by an LLM (Phase 2, via OpenRouter), indexed
for **semantic search by meaning** (Phase 3, local embeddings + ChromaDB), and
answerable through **chat-with-your-notes** (Phase 4, RAG). A web UI and voice
notes are planned for later phases.

> **Build status:** Phases 1–4 are implemented. See `PROJECT_STATUS.md` for
> the full roadmap and per-file status.

---

## Architecture

The code is layered so that dependencies only point **downward**:

```
routes  ->  services  ->  repositories  ->  models
 (HTTP)     (business)      (SQL only)       (ORM)
```

- A **router** never touches the database or contains business logic.
- A **service** never imports FastAPI (so it is reusable + unit-testable).
- A **repository** is the only place that runs queries.
- A **model** only describes the table shape.

Domain errors (`utils/exceptions.py`) are raised by services and translated
into consistent JSON responses in exactly one place (`main.py`).

### Project tree

```
ai-smart-notes/
├── app/
│   ├── api/routes/
│   │   ├── notes.py            # Notes HTTP endpoints + DI wiring
│   │   ├── tasks.py            # Tasks HTTP endpoints + DI wiring
│   │   ├── search.py           # GET /search — semantic search (Phase 3)
│   │   └── chat.py             # POST /chat — chat with notes / RAG (Phase 4)
│   ├── ai/                     # AI layer (Phases 2–4)
│   │   ├── schemas.py          # Category/Priority enums + NoteAnalysis
│   │   ├── prompts.py          # Categorization prompt + template
│   │   ├── llm.py              # ChatOpenAI factory → OpenRouter
│   │   ├── categorizer.py      # analyze(): category + priority (never raises)
│   │   ├── embedding_models.py # VectorMetadata / SearchResult DTOs
│   │   ├── embedding_service.py# sentence-transformers wrapper (text → vector)
│   │   ├── rag_prompts.py      # Grounded RAG chat prompt (Phase 4)
│   │   └── rag.py              # RAGService: retrieve → generate answer (Phase 4)
│   ├── vectordb/               # Vector store layer (Phase 3)
│   │   ├── chroma_client.py    # Persistent ChromaDB client + collection
│   │   ├── vector_store.py     # upsert / delete / query on the collection
│   │   └── search.py           # Query → embed → retrieve → ranked results
│   ├── core/
│   │   ├── config.py           # Pydantic settings loaded from .env
│   │   └── database.py         # Engine, SessionLocal, Base, get_db()
│   ├── db/
│   │   └── base.py             # Imports all models for Alembic metadata
│   ├── models/
│   │   ├── mixins.py           # TimestampMixin (created_at/updated_at)
│   │   ├── note.py             # Note ORM model (+ category/priority)
│   │   └── task.py             # Task ORM model + TaskStatus enum
│   ├── schemas/
│   │   ├── note.py             # NoteCreate/Update/Response
│   │   ├── task.py             # TaskCreate/Update/StatusUpdate/Response
│   │   └── chat.py             # ChatRequest/ChatSource/ChatResponse (Phase 4)
│   ├── repositories/
│   │   ├── note_repository.py  # Notes SQL
│   │   └── task_repository.py  # Tasks SQL
│   ├── services/
│   │   ├── note_service.py     # Notes business logic (AI + vector hooks)
│   │   ├── note_embedding_service.py # Best-effort note → vector sync
│   │   └── task_service.py     # Tasks business logic
│   ├── utils/
│   │   └── exceptions.py       # AppError / NotFoundError / BadRequestError
│   └── main.py                 # App assembly, routers, error handlers
├── alembic/
│   ├── env.py                  # Migration runtime (URL + metadata wiring)
│   ├── script.py.mako          # Migration template
│   └── versions/
│       ├── 0001_initial_schema.py       # notes + tasks tables
│       └── 0002_add_note_ai_fields.py   # + category/priority columns
├── chroma_data/                # ChromaDB vectors on disk (git-ignored)
├── alembic.ini
├── .env.example                # Config template (committed)
├── .env                        # Real config (git-ignored)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Prerequisites

- **Python 3.11+** (the code uses `X | None` typing syntax).
- **PostgreSQL 13+** running locally (or reachable via `DATABASE_URL`).
- An **OpenRouter API key** (Phase 2 AI categorization runs on note create/update).
- **~1 GB free disk** for Phase 3: `sentence-transformers` pulls in PyTorch, and
  the embedding model weights (~80 MB) download once on first use, then cache
  locally. Everything runs on-device (CPU by default) — no embedding API cost.

---

## Local setup

### 1. Create and activate a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux (bash):**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env      # Windows PowerShell: copy .env.example .env
```
Two variables are **required** (the app refuses to start without them):
```
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/ai_smart_notes
OPENROUTER_API_KEY=sk-or-v1-your-key-here          # get one at https://openrouter.ai/keys
```
Everything else is **optional** and has a sensible default in `app/core/config.py`.
The AI and vector tunables (all overridable, never hardcoded):

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | Model slug for categorization |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `EMBEDDING_DEVICE` | `cpu` | `cpu` or `cuda` |
| `CHROMA_PERSIST_PATH` | `./chroma_data` | Where vectors are stored on disk |
| `CHROMA_COLLECTION_NAME` | `notes` | Chroma collection name |
| `SEARCH_TOP_K` | `5` | Default number of search results |

### 4. Create the database
```bash
createdb ai_smart_notes
# or, inside psql:  CREATE DATABASE ai_smart_notes;
```

### 5. Run migrations (creates the tables + enum)
```bash
alembic upgrade head
```
To roll back: `alembic downgrade base`.

### 6. Start the server
```bash
uvicorn app.main:app --reload
```

- Interactive API docs (Swagger UI): **http://127.0.0.1:8000/docs**
- Alternative docs (ReDoc): **http://127.0.0.1:8000/redoc**
- Health check: **http://127.0.0.1:8000/health**

All API routes are mounted under the prefix **`/api/v1`**.

---

## Deployment (Docker)

The whole stack runs in two containers via Docker Compose — the FastAPI
backend (`api`) and the React SPA served by nginx (`web`). **PostgreSQL is not
containerized**: the app uses Neon (remote), configured through `DATABASE_URL`
in `.env`.

### Prerequisites
- Docker Desktop (or Docker Engine) with Compose v2.
- A populated `.env` in the project root (copy from `.env.example`), including
  `DATABASE_URL` and `OPENROUTER_API_KEY`.

### Run it
```bash
docker compose up --build
```

- **Web app:** http://localhost:8080 &nbsp;(nginx serves the SPA and proxies
  `/api` + `/media` to the backend — one origin, no CORS)
- **API docs:** http://localhost:8000/docs

The `api` container runs `alembic upgrade head` on startup, so the schema is
brought current automatically. Stop with `Ctrl+C`, or `docker compose down`.

### Images & serving
- **`Dockerfile`** (API): `python:3.12-slim`, installs `requirements.txt` in a
  cached layer, copies `app/` + Alembic, then runs migrations and Uvicorn. A
  `HEALTHCHECK` hits `/health`.
- **`frontend/Dockerfile`** (web): multi-stage — Node builds the Vite bundle
  (`VITE_API_BASE_URL=/api/v1`, baked in for same-origin), then a small nginx
  image serves `dist/` using `frontend/nginx.conf` (SPA fallback + reverse
  proxy). `web` waits for `api` to report healthy before starting.

### Persistent data (volumes)
Runtime data lives in named volumes so it survives container rebuilds:

| Volume | Mount | Holds |
|--------|-------|-------|
| `chroma_data` | `/app/chroma_data` | Vector index (semantic search) |
| `media` | `/app/media` | Uploaded note images |

`docker compose down` keeps these; `docker compose down -v` deletes them.

> **First run note:** on the first semantic-search/note operation the API
> downloads the embedding model (`all-MiniLM-L6-v2`, ~80 MB) from Hugging Face,
> so the container needs outbound internet and that first call is slower.

---

## API reference & examples

Base URL: `http://127.0.0.1:8000/api/v1`

### Health

```bash
curl http://127.0.0.1:8000/health
```
```json
{ "status": "ok", "app": "AI Smart Notes", "version": "0.1.0" }
```

---

### Notes

A note: `id`, `title`, `content`, `is_pinned`, `created_at`, `updated_at`, plus
two **AI-assigned, read-only** fields — `category` (Work, Coding, Health, …) and
`priority` (High/Medium/Low). These are filled automatically on create and
re-derived when the title/content changes; if the LLM call fails they fall back
to `Other` / `Medium` and the note is still saved.

#### Create a note — `POST /notes`
```bash
curl -X POST http://127.0.0.1:8000/api/v1/notes \
  -H "Content-Type: application/json" \
  -d '{"title": "Groceries", "content": "Milk, eggs, bread"}'
```
**201 Created**
```json
{
  "title": "Groceries",
  "content": "Milk, eggs, bread",
  "id": 1,
  "is_pinned": false,
  "created_at": "2026-06-29T12:00:00+00:00",
  "updated_at": "2026-06-29T12:00:00+00:00"
}
```

#### List notes — `GET /notes?skip=0&limit=100`
Returns notes pinned-first, then newest-first.
```bash
curl "http://127.0.0.1:8000/api/v1/notes?skip=0&limit=20"
```
```json
[
  {
    "title": "Groceries",
    "content": "Milk, eggs, bread",
    "id": 1,
    "is_pinned": false,
    "created_at": "2026-06-29T12:00:00+00:00",
    "updated_at": "2026-06-29T12:00:00+00:00"
  }
]
```

#### Get one note — `GET /notes/{id}`
```bash
curl http://127.0.0.1:8000/api/v1/notes/1
```

#### Update a note (partial) — `PUT /notes/{id}`
Only the fields you send are changed.
```bash
curl -X PUT http://127.0.0.1:8000/api/v1/notes/1 \
  -H "Content-Type: application/json" \
  -d '{"content": "Milk, eggs, bread, coffee"}'
```

#### Pin / unpin a note — `PATCH /notes/{id}/pin`
```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/notes/1/pin \
  -H "Content-Type: application/json" \
  -d '{"pinned": true}'
```
```json
{
  "title": "Groceries",
  "content": "Milk, eggs, bread, coffee",
  "id": 1,
  "is_pinned": true,
  "created_at": "2026-06-29T12:00:00+00:00",
  "updated_at": "2026-06-29T12:05:00+00:00"
}
```

#### Delete a note — `DELETE /notes/{id}`
```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/notes/1 -i
```
**204 No Content** (empty body).

---

### Tasks

A task: `id`, `title`, `description`, `status`, `due_date`, `created_at`,
`updated_at`. `status` is one of `Pending` / `In Progress` / `Completed`
(new tasks start as `Pending`).

#### Create a task — `POST /tasks`
```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Submit assignment", "description": "Chapter 5", "due_date": "2026-07-01T18:00:00Z"}'
```
**201 Created**
```json
{
  "title": "Submit assignment",
  "description": "Chapter 5",
  "due_date": "2026-07-01T18:00:00+00:00",
  "id": 1,
  "status": "Pending",
  "created_at": "2026-06-29T12:00:00+00:00",
  "updated_at": "2026-06-29T12:00:00+00:00"
}
```

#### List tasks — `GET /tasks?skip=0&limit=100`
Newest-first.
```bash
curl "http://127.0.0.1:8000/api/v1/tasks?skip=0&limit=20"
```

#### Get one task — `GET /tasks/{id}`
```bash
curl http://127.0.0.1:8000/api/v1/tasks/1
```

#### Update a task (partial) — `PUT /tasks/{id}`
```bash
curl -X PUT http://127.0.0.1:8000/api/v1/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{"description": "Chapter 5 + appendix"}'
```

#### Change status — `PATCH /tasks/{id}/status`
```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/tasks/1/status \
  -H "Content-Type: application/json" \
  -d '{"status": "In Progress"}'
```
```json
{
  "title": "Submit assignment",
  "description": "Chapter 5 + appendix",
  "due_date": "2026-07-01T18:00:00+00:00",
  "id": 1,
  "status": "In Progress",
  "created_at": "2026-06-29T12:00:00+00:00",
  "updated_at": "2026-06-29T12:10:00+00:00"
}
```

#### Delete a task — `DELETE /tasks/{id}`
```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/tasks/1 -i
```
**204 No Content**.

---

## Semantic search (Phase 3)

Search notes by **meaning**, not keywords. Searching `"learn backend"` finds a
note about `"study FastAPI and SQLAlchemy"`, ranked by how close the meanings are.

### How it works

Notes are embedded locally with **sentence-transformers** (`all-MiniLM-L6-v2`)
and stored in a local, disk-persisted **ChromaDB** collection. PostgreSQL stays
the single source of truth; the vector index is **best-effort** — if Chroma or
the embedding model fails, note create/update/delete still succeed (the failure
is logged, never surfaced).

```
WRITE  (on note create / update / delete)
  note_service ─► note_embedding_service ─► embedding_service (text → vector)
                                        └─► vector_store ─► chroma_client ─► ChromaDB (disk)

QUERY  (GET /search)
  search router ─► SearchService ─► embedding_service (query → vector)
                               └─► vector_store ─► ChromaDB ─► ranked SearchResults (similarity %)
```

- **Sync:** the vector id is `str(note_id)`, so an update is an upsert and a
  delete removes the vector — create and update share one code path.
- **Score:** Chroma's cosine distance is converted to a `similarity_score`
  percentage (0–100, higher = closer) and results are sorted high→low.
- **Metadata:** each vector stores `note_id`, `title`, `category`, `priority`,
  `created_at`, `updated_at`, which are returned with every hit.

### Search notes — `GET /search`

Query parameters:

| Param | Required | Description |
|-------|----------|-------------|
| `query` | yes | Free-text query (non-empty; empty → 422). |
| `top_k` | no | Max results, 1–50. Defaults to `SEARCH_TOP_K` (5). |

```bash
curl "http://127.0.0.1:8000/api/v1/search?query=learn%20backend&top_k=3"
```
**200 OK** — ranked most-similar first:
```json
[
  {
    "note_id": 7,
    "title": "Study plan",
    "content": "Study FastAPI and SQLAlchemy this week",
    "category": "Coding",
    "priority": "High",
    "created_at": "2026-07-10T09:00:00+00:00",
    "updated_at": "2026-07-10T09:00:00+00:00",
    "similarity_score": 71
  }
]
```

> **First run:** the embedding model weights (~80 MB) download once and are then
> cached; the first search (or first note created) after startup pays that
> one-time cost. Vectors persist under `CHROMA_PERSIST_PATH` (`./chroma_data`)
> across restarts. Notes created **before** Phase 3 aren't indexed until they
> are next created/updated; re-saving a note (any edit) indexes it.

### Scaling notes

- **Re-indexing:** changing `EMBEDDING_MODEL` changes the vector dimensionality —
  the existing `chroma_data/` must be rebuilt (delete it and re-save notes, or
  add a backfill script).
- **GPU:** set `EMBEDDING_DEVICE=cuda` to embed on a compatible GPU.
- **Throughput:** embedding is synchronous on the request thread today; for high
  write volume, move indexing to a background worker/queue.
- **Production:** run Chroma as a persistent server (or a managed vector DB) with
  a durable volume instead of the embedded on-disk mode used here.

---

## Chat with notes (Phase 4)

Ask a natural-language question and get an answer grounded **only** in your own
notes, along with the notes it used. This is retrieval-augmented generation
(RAG): the question is answered by first retrieving the relevant notes (Phase 3
search) and then having the LLM (Phase 2, OpenRouter) answer using just those.

### How it works

```
POST /chat
  chat router ─► RAGService.ask()
                   ├─► SearchService   (retrieve the most relevant notes)   [Phase 3]
                   ├─► rag_prompts      (format notes into a grounded prompt)
                   └─► LLM → StrOutputParser  (generate the answer)          [Phase 2]
                   ◄─ ChatResponse { answer, sources }
```

- **Grounded:** the prompt instructs the model to answer only from the retrieved
  notes and to say so when the notes don't contain the answer — it does not fall
  back on outside knowledge or invent details.
- **Sources returned:** every answer comes with the notes it was built from, so
  you can verify it and link back to the originals.
- **No relevant notes → honest answer:** if retrieval finds nothing, you get
  `"I couldn't find anything relevant in your notes to answer that."` and an
  empty `sources` list — and no LLM call is made.
- **Failures surface:** unlike categorization (which degrades to safe defaults),
  a generation failure returns a 500 rather than a fabricated answer.

### Ask a question — `POST /chat`

Request body:

| Field | Required | Description |
|-------|----------|-------------|
| `question` | yes | Natural-language question (non-empty; empty → 422). |
| `top_k` | no | How many notes to retrieve as context, 1–20. Defaults to `SEARCH_TOP_K` (5). |

```bash
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What did I plan to study this week?"}'
```
**200 OK**
```json
{
  "answer": "You planned to study FastAPI and SQLAlchemy this week.",
  "sources": [
    { "note_id": 7, "title": "Study plan", "similarity_score": 71 }
  ]
}
```

When nothing relevant is found:
```json
{
  "answer": "I couldn't find anything relevant in your notes to answer that.",
  "sources": []
}
```

> Chat reads from the same ChromaDB index that semantic search uses, so only
> notes that have been indexed (created/updated since Phase 3) are searchable.
> The context handed to the model is bounded, so very long or numerous notes are
> truncated to the most relevant ones.

---

## Error responses

All errors return a consistent JSON shape: `{"detail": "..."}`.

| Status | When | Example body |
|--------|------|--------------|
| **404 Not Found** | Unknown note/task id | `{"detail": "Note with id 5 was not found."}` |
| **422 Unprocessable Entity** | Request body fails validation (e.g. empty title, invalid status) | FastAPI's detailed validation error |
| **400 Bad Request** | Business-rule violation (reserved for future use) | `{"detail": "..."}` |
| **500 Internal Server Error** | Unexpected error (logged server-side; no internals leaked) | `{"detail": "Internal Server Error"}` |

Example 404:
```bash
curl -i http://127.0.0.1:8000/api/v1/notes/999
```
```
HTTP/1.1 404 Not Found
{"detail": "Note with id 999 was not found."}
```

---

## What's next (later phases)

Phases 1–4 are built (CRUD, AI categorization/priority, semantic search, and
chat-with-notes / RAG). Remaining:

- **Phase 5:** React frontend, voice notes, and deployment
  (containerization, hosted Postgres, a persistent Chroma volume).

See `PROJECT_STATUS.md` for the detailed, per-file roadmap.
```
