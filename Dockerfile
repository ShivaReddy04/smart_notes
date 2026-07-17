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
# torch ship prebuilt wheels, so no compiler/system libs are required.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps FIRST so this layer is cached and only rebuilds when
# requirements.txt changes — not on every code edit.
#
# CPU-only PyTorch: sentence-transformers depends on torch, and the DEFAULT
# torch wheel bundles ~2-3 GB of CUDA/NVIDIA GPU libraries. This deployment
# runs on CPU (EMBEDDING_DEVICE=cpu), so we install the CPU build from
# PyTorch's CPU wheel index FIRST. That satisfies the torch dependency, so the
# subsequent requirements install pulls no GPU stack — keeping the image lean.
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install -r requirements.txt

# Copy the application code and the Alembic migration tooling.
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini

# Create the runtime data directories. In compose these paths are also backed
# by named volumes so their contents persist across container replacements.
RUN mkdir -p media chroma_data

EXPOSE 8000

# Liveness probe hitting the app's own /health endpoint. start-period gives the
# process time to boot (and to lazily load the embedding model on first use).
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Apply any pending migrations, THEN start the server. Running `alembic upgrade
# head` here keeps a single-container deploy self-updating; for a multi-replica
# setup you would move migrations into a one-shot job so only one runner applies
# them. Neon (remote) is the target, so no local DB is started.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
