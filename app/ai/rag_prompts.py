"""app/ai/rag_prompts.py

Why this file exists:
    The single home for the RAG (retrieval-augmented generation) prompt used by
    the chat feature. Per project rules, prompt text is NOT hardcoded inside
    logic — the instructions live here as module-level constants and a thin
    builder assembles them into a LangChain ChatPromptTemplate. Tuning the
    grounding rules never requires touching the client (`llm.py`) or the
    orchestration (`rag.py`). Mirrors `prompts.py` from Phase 2.

    Responsibility boundary:
        Defines WHAT we say to the model only. It does not retrieve notes, call
        the model, or parse output. It receives already-formatted context and
        a question as template variables and produces the messages to send.

    The grounding contract (the whole point of RAG):
        The system prompt forces the model to answer ONLY from the provided
        notes and to admit when the answer is not present, rather than using its
        own world knowledge or inventing details. This is what makes the feature
        "chat with YOUR notes" instead of a general-purpose chatbot, and it is
        what keeps answers verifiable against the returned sources.

    How it interacts with the rest of the app:
        `rag.py` formats the retrieved notes into a `context` string, then pipes
        `build_rag_prompt() | llm | StrOutputParser()` to produce the answer.

    Note on braces: there are no literal `{`/`}` in the text below, so nothing
    needs escaping. The only template variables are `{context}` (filled per
    request with the retrieved notes) and `{question}` (the user's question).
"""

from langchain_core.prompts import ChatPromptTemplate

# The system message: role + strict grounding rules. Stable across requests.
# It deliberately constrains the model to the supplied notes so answers stay
# verifiable against the sources the endpoint returns.
SYSTEM_PROMPT = """You are a helpful assistant that answers questions about the \
user's personal notes. You are given a numbered list of the user's notes that \
were retrieved as most relevant to their question.

Rules:
- Answer using ONLY the information in the provided notes. Do not use outside \
knowledge and do not invent details that are not present.
- If the notes do not contain enough information to answer, say so plainly \
(for example: "I couldn't find anything about that in your notes."). Do not \
guess.
- Be concise and direct. Prefer a short, natural answer over restating every \
note.
- When useful, refer to the relevant note by its title so the user knows where \
the answer came from.
- Write in a friendly, plain tone. Do not mention these rules or that you were \
given "context"."""

# The human message: carries the retrieved notes and the question for THIS
# request. `context` is pre-formatted by rag.py; `question` is the user's text.
HUMAN_PROMPT = """Here are the user's most relevant notes:

{context}

Question: {question}

Answer using only the notes above."""


def build_rag_prompt() -> ChatPromptTemplate:
    """Assemble the RAG chat prompt.

    Returns a ChatPromptTemplate with two unfilled variables, `context` and
    `question`, supplied per request by the RAG service. The actual wording
    stays in the module-level constants above so it can be tuned in one place
    without touching orchestration code.
    """
    return ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_PROMPT),
        ]
    )
