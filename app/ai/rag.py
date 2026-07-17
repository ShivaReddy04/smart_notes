"""app/ai/rag.py

Why this file exists:
    The orchestration heart of the chat feature (Phase 4, RAG). It composes the
    two halves of retrieval-augmented generation — retrieve the most relevant
    notes, then generate a grounded answer from them — behind a single entry
    point, `ask(question) -> ChatResponse`, that the /chat route calls.

    It is the chat-side analogue of the categorizer: where the categorizer wires
    prompt | llm | parser to classify a note, this wires retrieval + prompt |
    llm | parser to answer a question about many notes. It reuses, rather than
    re-implements, the two subsystems already built:
        * Phase 3 SearchService — turns the question into ranked note hits.
        * Phase 2 get_llm()      — the OpenRouter-backed chat client.

    Responsibility boundary:
        Orchestration + context assembly only. It does not embed text or query
        Chroma (SearchService does), define prompt wording (rag_prompts does),
        or map HTTP (the route does). It sequences them and turns note hits into
        the `{context}` the prompt expects.

    Two deliberate reliability policies:
        * Empty context is GRACEFUL. If no relevant notes are found AND the user
          has no tasks, we return an honest "nothing found" answer with empty
          sources and DO NOT call the LLM — a generation with no grounding cannot
          be trusted, so we skip it. (Tasks alone are enough to answer, so we
          still generate when notes are empty but tasks exist.)
        * Generation failure SURFACES. Unlike the categorizer (which falls back
          to safe defaults so CRUD never breaks), a failed chat answer must not
          be faked. Exceptions propagate to main.py's catch-all handler as a
          uniform 500 — mirroring search.py's "never disguise a failure as no
          results" stance. There is no useful safe-default answer to invent.

    How it interacts with the rest of the app:
        The /chat route depends on `get_rag_service()` and calls `ask()`, then
        returns the ChatResponse (FastAPI serializes it via response_model).
"""

import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser

from app.ai.embedding_models import SearchResult
from app.ai.llm import get_llm
from app.ai.rag_prompts import build_rag_prompt
from app.core.config import get_settings
from app.models.task import Task
from app.schemas.chat import ChatResponse, ChatSource
from app.vectordb.search import SearchService, get_search_service

# Dedicated logger so chat activity/failures are easy to filter; reuses the
# logging configuration set up in main.py.
logger = logging.getLogger("ai_smart_notes.rag")

# Upper bound on the characters of note context handed to the model, so a large
# or numerous set of notes cannot blow the token budget or latency. Mirrors the
# categorizer's MAX_INPUT_CHARS cap (a module constant, not a tunable setting).
MAX_CONTEXT_CHARS = 6000

# Separate, smaller cap for the tasks block. Tasks are one-liners (status +
# title + due date), so they need far less room than note bodies; bounding them
# on their own keeps a long to-do list from crowding out the note context.
MAX_TASKS_CHARS = 2000

# The honest answer returned when there is nothing to ground on (no relevant
# notes and no tasks). Kept as a constant so the "no grounding" response is
# defined in exactly one place.
NO_CONTEXT_ANSWER = (
    "I couldn't find anything relevant in your notes or tasks to answer that."
)


class RAGService:
    """Answers questions about the user's notes via retrieval-augmented generation.

    Stateless apart from its injected collaborators. Injecting them (rather than
    reaching for the module singletons directly) keeps the service unit-testable
    with fakes and follows the DI shape used across the app.
    """

    def __init__(self, search_service: SearchService, llm: BaseChatModel) -> None:
        """Wire in retrieval and generation.

          * `search_service` -> retrieves the notes most relevant to a question.
          * `llm`            -> the OpenRouter chat client used to generate.

        The generation chain (prompt | llm | parser) is built once here so
        repeated `ask` calls reuse it. StrOutputParser (not a Pydantic parser)
        because a chat answer is free text, unlike the categorizer's JSON.
        """
        self._search_service = search_service
        self._chain = build_rag_prompt() | llm | StrOutputParser()

    @staticmethod
    def _format_context(hits: list[SearchResult]) -> str:
        """Render retrieved notes into the numbered context block the prompt expects.

        Each note becomes a titled, numbered entry with its body, so the model
        can attribute answers to a specific note. Entries are added whole until
        MAX_CONTEXT_CHARS would be exceeded, then we stop — bounding the context
        without slicing a note mid-sentence (hits are already ranked most-
        relevant first, so the least-relevant notes are the ones dropped).
        """
        blocks: list[str] = []
        used = 0
        for index, hit in enumerate(hits, start=1):
            body = (hit.content or "").strip() or "(no content)"
            block = f"{index}. {hit.title}\n{body}"
            # +2 accounts for the blank line joined between entries.
            if used + len(block) + 2 > MAX_CONTEXT_CHARS and blocks:
                logger.debug("Context truncated at %d of %d notes", index - 1, len(hits))
                break
            blocks.append(block)
            used += len(block) + 2
        return "\n\n".join(blocks)

    @staticmethod
    def _format_tasks(tasks: list[Task]) -> str:
        """Render the user's tasks into the compact block the prompt expects.

        Each task becomes ONE numbered line carrying its status and (when set)
        its due date, e.g. "1. [Pending] Pay bill — before 5pm (due 2026-07-18
        17:00)". A one-line-per-task shape (not the note-style title+body block)
        is what lets the model answer "what's pending / due" cleanly. Entries are
        added whole until MAX_TASKS_CHARS would be exceeded, then we stop —
        bounding the block the same way _format_context bounds notes. Tasks are
        passed newest-first, so the oldest are the ones dropped.
        """
        if not tasks:
            # A real, explicit value (not "") so the prompt's {tasks} slot never
            # renders blank and the model knows there are simply no tasks.
            return "(no tasks)"

        lines: list[str] = []
        used = 0
        for index, task in enumerate(tasks, start=1):
            description = (task.description or "").strip()
            detail = f" — {description}" if description else ""
            due = f" (due {task.due_date:%Y-%m-%d %H:%M})" if task.due_date else ""
            # .value -> the human-readable status string ("In Progress"), not the
            # enum member repr.
            line = f"{index}. [{task.status.value}] {task.title}{detail}{due}"
            if used + len(line) + 1 > MAX_TASKS_CHARS and lines:
                logger.debug("Task block truncated at %d of %d tasks", index - 1, len(tasks))
                break
            lines.append(line)
            used += len(line) + 1
        return "\n".join(lines)

    @staticmethod
    def _to_sources(hits: list[SearchResult]) -> list[ChatSource]:
        """Project the retrieved hits into the slim ChatSource shape returned to
        the client — just enough (id, title, score) to prove grounding and link
        back, without echoing note bodies the client already owns."""
        return [
            ChatSource(
                note_id=hit.note_id,
                title=hit.title,
                similarity_score=hit.similarity_score,
            )
            for hit in hits
        ]

    def ask(
        self,
        question: str,
        top_k: int | None = None,
        tasks: list[Task] | None = None,
    ) -> ChatResponse:
        """Answer `question` using the user's notes AND tasks as grounding.

        Steps:
            1. Guard empty input -> honest "nothing found" answer (no work).
            2. Retrieve the most relevant notes (SearchService).
            3. If nothing relevant was found AND there are no tasks -> "nothing
               found" answer, no LLM call (there is nothing to ground on).
            4. Otherwise format the notes + tasks into context, invoke the chain,
               and return the generated answer plus the note sources it used.

        `top_k` falls back to the configured `search_top_k` when omitted. `tasks`
        is the user's task list, supplied by the route (the RAG service has no DB
        session of its own); when omitted the chat behaves exactly as before.
        Any failure during generation propagates (a 500), never a fabricated
        answer.
        """
        if not question or not question.strip():
            # Defense in depth: the schema already rejects empty questions, but
            # the service stays correct if called from a non-HTTP caller.
            return ChatResponse(answer=NO_CONTEXT_ANSWER, sources=[])

        limit = top_k if top_k is not None else get_settings().search_top_k
        hits = self._search_service.search(query=question, top_k=limit)

        tasks = tasks or []
        if not hits and not tasks:
            logger.debug("Chat found no relevant notes and no tasks; returning no-context answer")
            return ChatResponse(answer=NO_CONTEXT_ANSWER, sources=[])

        # With tasks but no matching notes we still answer — the tasks alone are
        # valid grounding. A placeholder keeps the notes slot non-empty so the
        # model reads it as "no relevant notes", not a malformed prompt.
        context = self._format_context(hits) if hits else "(no relevant notes found)"
        tasks_block = self._format_tasks(tasks)
        # No try/except: a generation failure must surface as an error, not be
        # disguised as an answer (see this module's reliability policy).
        answer = self._chain.invoke(
            {"context": context, "tasks": tasks_block, "question": question.strip()}
        )
        logger.debug("Chat answered from %d note(s) and %d task(s)", len(hits), len(tasks))

        # Sources remain the retrieved NOTES only (they carry a similarity score);
        # tasks are grounding but not a scored "source", so they are not listed.
        return ChatResponse(answer=answer.strip(), sources=self._to_sources(hits))


# Module-level singleton, populated lazily so importing this module never
# constructs the embedding client, the vector store, or the LLM.
_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    """Return the process-wide RAGService, building it once.

    Wires the shared SearchService and LLM into a RAGService. Cached per
    process, mirroring the other get_*() accessors. The /chat route depends on
    this accessor, not on the collaborators directly.
    """
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService(get_search_service(), get_llm())
    return _rag_service
