"""app/schemas/chat.py

Why this file exists:
    Defines the API contract for the chat-with-notes feature (Phase 4, RAG) —
    the Pydantic models that validate the incoming question and serialize the
    outgoing answer. It is the HTTP-side translation boundary, the exact mirror
    of `schemas/note.py`, but for the chat endpoint.

    Responsibility boundary:
        Shape + validation of data crossing the /chat boundary only. It knows
        nothing about retrieval (that is the vector store), generation (that is
        the LLM), or orchestration (that is the RAG service). Keeping the wire
        shape separate lets the RAG internals evolve without changing clients.

    The three-model split mirrors the request/response contract:
        * ChatRequest  — what a client MAY send (a question + optional top_k).
        * ChatSource   — one note that grounded the answer (proof of grounding).
        * ChatResponse — what the server ALWAYS returns (answer + its sources).

    Why sources are returned:
        RAG's defining property is grounding. Echoing back the notes the answer
        was built from lets a client verify the answer and link to the originals,
        rather than trusting an opaque generation. This is what separates
        "chat with YOUR notes" from a generic chatbot.

    How it interacts with the rest of the app:
        * The /chat router declares ChatRequest as its body and ChatResponse as
          its `response_model`, so FastAPI validates input and documents it.
        * The RAG service receives a validated question and returns a
          ChatResponse assembled from the retrieved notes + the LLM's answer.
"""

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """Request body for POST /chat.

    `str_strip_whitespace=True` trims the question before validation, so a
    question of "   " collapses to "" and fails `min_length=1` rather than
    reaching the retriever as blank.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    # The user's natural-language question. Required and non-empty: an empty
    # question is rejected at the boundary (422) rather than triggering an
    # embedding + retrieval round-trip that cannot produce a useful answer.
    question: str = Field(
        min_length=1,
        max_length=1000,
        description="Natural-language question to answer using your notes.",
        examples=["What did I plan to study this week?"],
    )

    # Optional override for how many notes to retrieve as context. When omitted
    # the RAG service applies the configured default (search_top_k). Bounded so
    # a client cannot request an unbounded context that blows the token budget.
    top_k: int | None = Field(
        default=None,
        ge=1,
        le=20,
        description="How many notes to retrieve as context. Defaults to the configured value.",
    )


class ChatSource(BaseModel):
    """One note that was used as grounding context for the answer.

    A deliberately slim projection of a search hit — just enough for a client
    to recognize and link back to the note (id + title) and to see how relevant
    it was (the similarity score). The full note body is intentionally NOT
    echoed here; the client already owns the notes and can fetch them by id.
    """

    note_id: int = Field(description="Primary key of the source note.")
    title: str = Field(description="Title of the source note.")
    similarity_score: int = Field(
        description="How closely this note matched the question (0-100, higher is closer).",
    )


class ChatResponse(BaseModel):
    """Response body for POST /chat.

    Carries the generated `answer` plus the `sources` that grounded it. When no
    relevant notes are found the RAG service returns a safe, explicit answer and
    an empty `sources` list rather than inventing content.
    """

    answer: str = Field(
        description="The grounded answer, generated only from the source notes.",
        examples=["You planned to study FastAPI and SQLAlchemy this week."],
    )
    sources: list[ChatSource] = Field(
        default_factory=list,
        description="The notes the answer was grounded in, most relevant first.",
    )
