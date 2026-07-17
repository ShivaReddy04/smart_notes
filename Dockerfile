# syntax=docker/dockerfile:1
#
# API image for AI Smart Notes (FastAPI + SQLAlchemy + AI stack).
#
# Why this file exists:
#   Packages the backend into a reproducible container so it runs the same on
#   any host. It installs dependencies in a cached layer, copies only the app
#   and migration tooling, applies DB migrations on startup, then serves the
#   API with Uvicorn.

FROM python:3.12-slim AS base

# Predictable Python behavior in containers:
#   * PYTHONUNBUFFERED     -> logs stream out immediately (no buffering).
#   * PYTHONDONTWRITEBYTECODE -> no .pyc clutter in the image.
#   * PIP_NO_CACHE_DIR     -> smaller image (no pip download cache).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# curl is only needed for the container HEALTHCHECK below. psycopg2-binary and
# the remaining wheels are prebuilt, so no compiler/system libs are required.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps FIRST so this layer is cached and only rebuilds when
# requirements.txt changes — not on every code edit.
#
# NOTE: there is no torch/PyTorch here anymore. Embeddings are produced by a
# hosted API (see app/ai/embedding_service.py) and vectors live in Postgres via
# pgvector, so the image stays small and boots within a free-tier RAM limit.
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy the application code and the Alembic migration tooling.
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini

# Create the local media directory used by the "local" image-storage backend
# (dev / docker-compose). In production the backend is "r2" and this stays
# empty. Vectors no longer live on disk (they are in Postgres), so there is no
# chroma_data directory anymore.
RUN mkdir -p media

EXPOSE 8000

# Liveness probe hitting the app's own /health endpoint. start-period gives the
# process time to run migrations and start Uvicorn.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Apply any pending migrations, THEN start the server. Running `alembic upgrade
# head` here keeps a single-container deploy self-updating; for a multi-replica
# setup you would move migrations into a one-shot job so only one runner applies
# them. Neon (remote) is the target, so no local DB is started.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
