---
title: AI Smart Notes API
emoji: 📝
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 8000
pinned: false
---

<!--
  The YAML block above configures this repo as a Hugging Face Space (free hosting).
    * sdk: docker   -> HF builds and runs the Dockerfile in this repo.
    * app_port: 8000 -> HF exposes the port uvicorn listens on (see Dockerfile CMD),
                        instead of the HF default of 7860.
  Secrets (DATABASE_URL, OPENROUTER_API_KEY, EMBEDDING_API_KEY, the S3_* vars,
  CORS_ORIGINS) are NOT set here — add them in the Space's Settings -> Variables
  and secrets; HF injects them as env vars at runtime. This block is ignored by
  GitHub/Render, so the repo works in all three places.
  NOTE: the primary, documented deploy target is Render (see render.yaml and the
  "Deployment — Render (free tier)" section below).
-->

# AI Smart Notes — Backend

A production-structured FastAPI + PostgreSQL backend for notes and tasks,
built with Clean Architecture. Beyond CRUD, every note is automatically
**categorized and prioritized** by an LLM (Phase 2, via OpenRouter), indexed
for **semantic search by meaning** (Phase 3, hosted Gemini embeddings +
Postgres `pgvector`), and answerable through **chat-with-your-notes**
(Phase 4, RAG). A React web UI (Phase 5) and image attachments are included.

> **Build status:** Phases 1–5 are implemented. The stack is designed to run on
> **Render's free tier** end-to-end (no torch, no persistent disk). See
> `PROJECT_STATUS.md` for the full roadmap and per-file status.

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
│   │   ├── chat.py             # POST /chat — chat with notes / RAG (Phase 4)
│   │   └── note_images.py      # Image upload/list/delete (Phase 5)
│   ├── ai/                     # AI layer (Phases 2–4)
│   │   ├── schemas.py          # Category/Priority enums + NoteAnalysis
│   │   ├── prompts.py          # Categorization prompt + template
│   │   ├── llm.py              # ChatOpenAI factory → OpenRouter
│   │   ├── categorizer.py      # analyze(): category + priority (never raises)
│   │   ├── embedding_models.py # VectorMetadata / SearchResult DTOs
│   │   ├── embedding_service.py# Hosted embeddings (Gemini) via OpenAIEmbeddings
│   │   ├── rag_prompts.py      # Grounded RAG chat prompt (Phase 4)
│   │   └── rag.py              # RAGService: retrieve → generate answer (Phase 4)
│   ├── vectordb/               # Vector store layer (Phase 3, pgvector)
│   │   ├── vector_store.py     # upsert / delete / query in Postgres (pgvector)
│   │   └── search.py           # Query → embed → retrieve → ranked results
│   ├── core/
│   │   ├── config.py           # Pydantic settings loaded from .env
│   │   └── database.py         # Engine, SessionLocal, Base, get_db()
│   ├── db/
│   │   └── base.py             # Imports all models for Alembic metadata
│   ├── models/
│   │   ├── mixins.py           # TimestampMixin (created_at/updated_at)
│   │   ├── note.py             # Note ORM model (+ category/priority)
│   │   ├── note_embedding.py   # NoteEmbedding: note_id + pgvector column (Phase 3)
│   │   ├── note_image.py       # NoteImage: image metadata rows (Phase 5)
│   │   └── task.py             # Task ORM model + TaskStatus enum
│   ├── schemas/
│   │   ├── note.py             # NoteCreate/Update/Response
│   │   ├── task.py             # TaskCreate/Update/StatusUpdate/Response
│   │   ├── chat.py             # ChatRequest/ChatSource/ChatResponse (Phase 4)
│   │   └── note_image.py       # NoteImageResponse (+ computed public url)
│   ├── repositories/
│   │   ├── note_repository.py  # Notes SQL
│   │   ├── note_image_repository.py # Note-image rows SQL
│   │   └── task_repository.py  # Tasks SQL
│   ├── services/
│   │   ├── note_service.py     # Notes business logic (AI + vector hooks)
│   │   ├── note_embedding_service.py # Best-effort note → vector sync
│   │   ├── image_storage_service.py  # Local-disk / S3 (Supabase) image bytes
│   │   ├── note_image_service.py     # Image use-cases (file + row consistency)
│   │   └── task_service.py     # Tasks business logic
│   ├── utils/
│   │   └── exceptions.py       # AppError / NotFoundError / BadRequestError
│   └── main.py                 # App assembly, routers, error handlers
├── alembic/
│   ├── env.py                  # Migration runtime (URL + metadata wiring)
│   ├── script.py.mako          # Migration template
│   └── versions/
│       ├── 0001_initial_schema.py       # notes + tasks tables
│       ├── 0002_add_note_ai_fields.py   # + category/priority columns
│       ├── 0003_add_note_images.py      # note_images table (Phase 5)
│       └── 0004_add_note_embeddings.py  # pgvector extension + note_embeddings
├── frontend/                   # React + Vite SPA (Phase 5)
├── Dockerfile                  # API image (no torch — hosted embeddings)
├── render.yaml                 # Render Blueprint (free-tier deploy)
├── docker-compose.yml          # Local full-stack (api + web)
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
- **PostgreSQL 13+ with the `pgvector` extension** available, reachable via
  `DATABASE_URL`. [Neon](https://neon.tech) works out of the box (it ships
  pgvector, and migration `0004` runs `CREATE EXTENSION IF NOT EXISTS vector`).
- An **OpenRouter API key** — Phase 2 AI categorization + Phase 4 chat.
- An **embeddings API key** — Phase 3 semantic search. The default provider is
  **Google Gemini** (free); get a key at
  [aistudio.google.com/apikey](https://aistudio.google.com/apikey). Embeddings
  are called over HTTP (no local model, no torch), so nothing heavy is installed.
- **(Optional) Supabase Storage** (or any S3-compatible provider) — only needed
  to store note-image uploads in the cloud (`IMAGE_STORAGE_BACKEND=s3`). Local
  dev defaults to disk and needs none.

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
Three variables are **required** (the app refuses to start without them):
```
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/db   # a pgvector-capable Postgres (e.g. Neon)
OPENROUTER_API_KEY=sk-or-v1-your-key-here      # chat + categorization — https://openrouter.ai/keys
EMBEDDING_API_KEY=your-gemini-key-here         # embeddings — https://aistudio.google.com/apikey
```
Everything else is **optional** and has a sensible default in `app/core/config.py`.
The AI, vector, and storage tunables (all overridable, never hardcoded):

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | Model slug for categorization/chat |
| `EMBEDDING_BASE_URL` | Gemini's OpenAI-compatible endpoint | Where embeddings are called |
| `EMBEDDING_MODEL` | `text-embedding-004` | Hosted embedding model |
| `EMBEDDING_DIMENSIONS` | `768` | Vector width — **must match** the `note_embeddings` column |
| `SEARCH_TOP_K` | `5` | Default number of search results |
| `IMAGE_STORAGE_BACKEND` | `local` | `local` (disk) or `s3` (Supabase/R2/S3) |
| `MEDIA_DIR` | `./media` | Local image dir (when backend is `local`) |
| `S3_REGION` | `us-east-1` | Storage region (Supabase project region; `auto` for R2) |
| `S3_ENDPOINT_URL` / `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` / `S3_BUCKET` / `S3_PUBLIC_BASE_URL` | — | S3 config (when backend is `s3`) |

> **Vector dimensions:** `EMBEDDING_DIMENSIONS` must equal the `vector(N)` column
> width created by migration `0004` (768 for Gemini `text-embedding-004`).
> Switching to a model with a different width means resizing that column and
> re-embedding existing notes.

### 4. Create the database
```bash
createdb ai_smart_notes
# or, inside psql:  CREATE DATABASE ai_smart_notes;
```

### 5. Run migrations (creates the tables, enum, and pgvector index)
```bash
alembic upgrade head
```
This also runs `CREATE EXTENSION IF NOT EXISTS vector`, so the database role
must be allowed to create extensions (Neon's default role is; for a local
Postgres you may need the `pgvector` package installed first). To roll back:
`alembic downgrade base`.

### 6. Start the server
```bash
uvicorn app.main:app --reload
```

- Interactive API docs (Swagger UI): **http://127.0.0.1:8000/docs**
- Alternative docs (ReDoc): **http://127.0.0.1:8000/redoc**
- Health check: **http://127.0.0.1:8000/health**

All API routes are mounted under the prefix **`/api/v1`**.

---

## Deployment — Render (free tier)

The stack is designed to run **entirely on Render's free tier**. The three
things that used to require paid resources were removed by design:

- **No torch** — embeddings are a hosted API call (Gemini), so the API fits the
  free **512 MB RAM** limit.
- **No persistent disk** — vectors live in Postgres (`pgvector`, on Neon) and
  image bytes live in **Supabase Storage** (S3-compatible). The free tier has no disks.
- **Free static frontend** — the React SPA is served from Render's CDN.

Everything is declared in **`render.yaml`** (a Render Blueprint): one Docker
`api` service and one static `web` service.

### Steps

1. **Get credentials:** a free [Gemini key](https://aistudio.google.com/apikey)
   (embeddings) and a [Supabase](https://supabase.com) project with a **public**
   Storage bucket + **S3 Access Keys** (Storage → S3 Access Keys) for images.
   Your Neon `DATABASE_URL` and OpenRouter key you already have.
2. **Push to GitHub**, then in Render: **New + → Blueprint →** pick this repo.
   It reads `render.yaml` and provisions both services.
3. On the **api** service, set the secret env vars (marked `sync:false` in the
   Blueprint): `DATABASE_URL`, `OPENROUTER_API_KEY`, `EMBEDDING_API_KEY`, the
   five `S3_*` vars, and `CORS_ORIGINS` (`S3_REGION` is preset in the Blueprint).
4. On the **web** service, set `VITE_API_BASE_URL` to the api URL **+ `/api/v1`**
   (e.g. `https://<api>.onrender.com/api/v1`). Then set `CORS_ORIGINS` on the api
   to the web origin (JSON array) and redeploy.

The api container runs `alembic upgrade head` on first boot, which creates the
`vector` extension + `note_embeddings` table on Neon automatically.

> **Free-tier caveat:** a free web service **spins down after ~15 min idle**; the
> next request wakes it (~50 s cold start). Fine for personal / demo use.

### Local full stack (Docker Compose)

For running the whole thing locally, `docker-compose.yml` builds the FastAPI
`api` and the nginx-served React `web`. **PostgreSQL is not containerized** — it
uses your remote `DATABASE_URL` (Neon).

```bash
docker compose up --build
```
- **Web app:** http://localhost:8080 (nginx serves the SPA and proxies `/api`)
- **API docs:** http://localhost:8000/docs

The `api` container runs migrations on startup. A single `media` named volume
persists local-disk image uploads (unused if you set `IMAGE_STORAGE_BACKEND=s3`);
vectors are in Postgres, so there is no vector volume. `docker compose down`
keeps the volume; `-v` deletes it.

> **First run note:** the first note/search call makes a network request to the
> embeddings API (Gemini), so the container needs outbound internet. There is no
> model download and no local disk warm-up.

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

Notes are embedded by a **hosted embeddings API** (Google Gemini,
`text-embedding-004`) and the resulting vectors are stored in **Postgres via
`pgvector`** — the same database as the notes, so there is no separate vector
service and no disk. PostgreSQL stays the single source of truth; the vector
index is **best-effort** — if the embeddings API or the vector write fails, note
create/update/delete still succeed (the failure is logged, never surfaced).

```
WRITE  (on note create / update / delete)
  note_service ─► note_embedding_service ─► embedding_service (text → vector, Gemini)
                                        └─► vector_store ─► note_embeddings (pgvector)

QUERY  (GET /search)
  search router ─► SearchService ─► embedding_service (query → vector, Gemini)
                               └─► vector_store ─► pgvector <=> + JOIN notes ─► ranked results
```

- **Sync:** the vector row is keyed on `note_id`, so an update is an upsert and a
  delete removes the row — create and update share one code path.
- **Score:** pgvector's cosine distance (`<=>`) is converted to a
  `similarity_score` percentage (0–100, higher = closer), sorted high→low.
- **Metadata:** the vector row stores only the embedding; each hit's `title`,
  `category`, `priority`, and timestamps come from a JOIN to the `notes` table,
  so results always reflect the note's current state.

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

> **Indexing:** each note is embedded via a network call to the embeddings API
> on create/update, then stored in the `note_embeddings` table. There is no model
> download. Notes created **before** Phase 3 aren't indexed until they are next
> created/updated; re-saving a note (any edit) indexes it.

### Scaling notes

- **Re-indexing:** changing the embedding model changes the vector
  dimensionality — update `EMBEDDING_DIMENSIONS`, resize the `note_embeddings`
  `vector(N)` column (a migration), and re-embed existing notes.
- **Index:** `note_embeddings` has an HNSW index (`vector_cosine_ops`) for fast
  approximate nearest-neighbour search as the table grows.
- **Throughput:** embedding is synchronous on the request thread today; for high
  write volume, move indexing to a background worker/queue.
- **Rate limits:** the embeddings API (Gemini free tier) is rate-limited; batch
  or back off for bulk re-indexing.

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

> Chat reads from the same pgvector index that semantic search uses, so only
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

Phases 1–5 are built: CRUD, AI categorization/priority, semantic search
(pgvector), chat-with-notes / RAG, a React frontend, image attachments
(Supabase Storage), and free-tier Render deployment. Remaining polish:

- **Production hardening:** background/queued embedding for high write volume,
  caching, and batching of embedding calls.

See `PROJECT_STATUS.md` for the detailed, per-file roadmap.
```
