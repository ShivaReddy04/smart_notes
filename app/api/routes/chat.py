"""app/api/routes/chat.py

Why this file exists:
    The HTTP boundary for chat-with-notes (Phase 4, RAG) — the write-side mirror
    of the search router. Its only job is translation: take the validated
    ChatRequest, call RAGService.ask(), and return the ChatResponse. There is NO
    retrieval, NO prompt building, and NO LLM access here; all of that lives in
    the RAG service below this layer.

    Responsibility boundary:
        Request/response mapping only. Like the search router it needs no
        database session — retrieval reads note text from the vector store, so
        it depends solely on the cached RAGService singleton (declared via
        Depends so tests can override it).

    How it interacts with the rest of the app:
        * main.py includes this router under the global API prefix, exposing
          POST /api/v1/chat.
        * FastAPI validates the body against ChatRequest and serializes the
          result via `response_model=ChatResponse`.
        * On a generation failure the exception propagates to main.py's catch-all
          handler (a uniform 500) — a failed answer is never disguised as a real
          one (mirrors the search route's stance).
"""

from fastapi import APIRouter, Depends

from app.ai.rag import RAGService, get_rag_service
from app.schemas.chat import ChatRequest, ChatResponse

# `prefix` groups the route under /chat; `tags` groups it in the docs. The
# global /api/v1 prefix is applied once when main.py includes us.
router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "",
    response_model=ChatResponse,
    summary="Ask a question answered from your notes (RAG)",
)
def chat(
    payload: ChatRequest,
    service: RAGService = Depends(get_rag_service),
) -> ChatResponse:
    """Answer a natural-language question using the user's notes as grounding.

    The question is validated (non-empty) at the boundary. The RAG service
    retrieves the most relevant notes, generates an answer grounded only in
    them, and returns that answer alongside the source notes it used. When no
    relevant notes exist, the answer says so and `sources` is empty.
    """
    return service.ask(question=payload.question, top_k=payload.top_k)
