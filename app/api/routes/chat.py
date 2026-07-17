"""app/api/routes/chat.py

Why this file exists:
    The HTTP boundary for chat-with-notes (Phase 4, RAG) — the write-side mirror
    of the search router. Its only job is translation: take the validated
    ChatRequest, call RAGService.ask(), and return the ChatResponse. There is NO
    retrieval, NO prompt building, and NO LLM access here; all of that lives in
    the RAG service below this layer.

    Responsibility boundary:
        Request/response mapping only. It depends on the cached RAGService
        singleton for retrieval + generation, and — so chat can also answer
        about tasks — on a request-scoped TaskService (its own DB session, wired
        via get_task_service) to read the user's current tasks. The route reads
        the tasks and hands them to the service; it builds no task context and
        contains no task logic itself. Both dependencies are declared via Depends
        so tests can override them.

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
from app.api.deps import get_current_user
from app.api.routes.tasks import get_task_service
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.task_service import TaskService

# Upper bound on how many tasks we hand the RAG service per question. Tasks are
# fetched newest-first; the service further bounds them by character budget, so
# this is just a sane ceiling on the DB read (matches the tasks list default).
MAX_TASKS_FOR_CHAT = 100

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
    task_service: TaskService = Depends(get_task_service),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    """Answer a natural-language question using the user's notes AND tasks.

    The question is validated (non-empty) at the boundary. We load the user's
    current tasks (newest-first, capped) and pass them alongside the question:
    the RAG service retrieves the most relevant notes, adds the tasks as extra
    grounding, and generates an answer based only on that combined context —
    returned with the source notes it used. When neither a relevant note nor a
    task exists, the answer says so and `sources` is empty.
    """
    tasks = task_service.list_tasks(limit=MAX_TASKS_FOR_CHAT)
    return service.ask(
        question=payload.question,
        user_id=current_user.id,
        top_k=payload.top_k,
        tasks=tasks,
    )
