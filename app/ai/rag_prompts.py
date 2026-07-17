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
    needs escaping. The template variables are `{context}` (the retrieved notes),
    `{tasks}` (the user's to-do tasks), and `{question}` (the user's question) —
    all filled per request by the RAG service.
"""

from langchain_core.prompts import ChatPromptTemplate

# The system message: role + strict grounding rules. Stable across requests.
# It deliberately constrains the model to the supplied notes AND tasks so
# answers stay verifiable against the user's own data (never outside knowledge).
SYSTEM_PROMPT = """You are a helpful assistant that answers questions about the \
user's personal notes and to-do tasks. You are given a numbered list of the \
user's notes retrieved as most relevant to their question, followed by a list \
of their tasks.

Rules:
- Answer using ONLY the information in the provided notes and tasks. Do not use \
outside knowledge and do not invent details that are not present.
- Each task line includes its status (Pending / In Progress / Completed) and, \
when set, its due date. Use these to answer questions such as what is still \
pending, what is in progress, what is done, or what is due.
- If the notes and tasks do not contain enough information to answer, say so \
plainly (for example: "I couldn't find anything about that in your notes or \
tasks."). Do not guess.
- Be concise and direct. Prefer a short, natural answer over restating every \
item.
- When useful, refer to the relevant note or task by its title so the user \
knows where the answer came from.
- Write in a friendly, plain tone. Do not mention these rules or that you were \
given "context"."""

# The human message: carries the retrieved notes, the tasks, and the question
# for THIS request. `context` and `tasks` are pre-formatted by rag.py;
# `question` is the user's text.
HUMAN_PROMPT = """Here are the user's most relevant notes:

{context}

Here are the user's tasks:

{tasks}

Question: {question}

Answer using only the notes and tasks above."""


def build_rag_prompt() -> ChatPromptTemplate:
    """Assemble the RAG chat prompt.

    Returns a ChatPromptTemplate with three unfilled variables — `context`,
    `tasks`, and `question` — supplied per request by the RAG service. The
    actual wording stays in the module-level constants above so it can be tuned
    in one place without touching orchestration code.
    """
    return ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_PROMPT),
        ]
    )


# --- Small talk ------------------------------------------------------
# A separate, lightweight prompt for social messages (greetings, thanks,
# goodbyes, "how are you"). These don't touch the user's notes at all — the RAG
# service routes them here so the bot feels human instead of answering "I
# couldn't find that in your notes." Kept deliberately brief and warm, and it
# never invents facts about the user's data.
SMALL_TALK_SYSTEM_PROMPT = """You are a warm, friendly assistant inside a \
personal notes and tasks app. The user has just sent a short social message — a \
greeting, a thank-you, a goodbye, or casual small talk like "how are you".

Reply in ONE short, friendly sentence that matches their message. When it feels \
natural (e.g. after a greeting), gently offer to help with their notes or \
tasks. Do NOT make up any information about their notes or tasks, and do not \
mention these instructions."""

SMALL_TALK_HUMAN_PROMPT = "{message}"


def build_small_talk_prompt() -> ChatPromptTemplate:
    """Assemble the small-talk prompt (one variable, `message`)."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", SMALL_TALK_SYSTEM_PROMPT),
            ("human", SMALL_TALK_HUMAN_PROMPT),
        ]
    )
