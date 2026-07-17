"""app/api/routes/search.py

Why this file exists:
    The HTTP boundary for semantic search — the read-side mirror of the notes
    router. Its only job is translation: pull `query` and `top_k` off the
    request, call SearchService.search(), and return the ranked results. There
    is NO scoring, NO embedding, and NO Chroma access here; all of that lives
    in the search service below this layer.

    Responsibility boundary:
        Request/response mapping only. Unlike the notes router it needs no
        database session — search reads note content from the vector store's
        stored documents, so it depends solely on the cached SearchService
        singleton (declared via Depends so tests can override it).

    How it interacts with the rest of the app:
        * main.py includes this router under the global API prefix, exposing
          GET /api/v1/search.
        * FastAPI validates the query parameters and serializes each
          SearchResult via `response_model=list[SearchResult]`.
        * On failure the exception propagates to main.py's catch-all handler
          (a uniform 500) — a failed search is never disguised as "no results".
"""

from fastapi import APIRouter, Depends, Query

from app.ai.embedding_models import SearchResult
from app.api.deps import get_current_user
from app.models.user import User
from app.vectordb.search import SearchService, get_search_service

# `prefix` groups the route under /search; `tags` groups it in the docs. The
# global /api/v1 prefix is applied once when main.py includes us.
router = APIRouter(prefix="/search", tags=["Search"])


@router.get(
    "",
    response_model=list[SearchResult],
    summary="Semantic search over notes",
)
def search_notes(
    query: str = Query(
        ...,
        min_length=1,
        description="Free-text query; notes are ranked by meaning, not keywords.",
    ),
    top_k: int | None = Query(
        None,
        ge=1,
        le=50,
        description="Max results to return. Defaults to the configured search_top_k.",
    ),
    service: SearchService = Depends(get_search_service),
    current_user: User = Depends(get_current_user),
) -> list[SearchResult]:
    """Return the user's notes most similar in meaning to `query`, ranked high→low.

    Requires a valid token (401 otherwise) and searches ONLY the current user's
    notes. `query` is required and non-empty (empty is a 422 at the boundary).
    When `top_k` is omitted the service applies the configured default. Each
    result carries the note's metadata, its content, and a 0-100 similarity score.
    """
    return service.search(query=query, user_id=current_user.id, top_k=top_k)
