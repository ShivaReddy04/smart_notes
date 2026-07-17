"""app/ai/categorizer.py

Why this file exists:
    The orchestration heart of the AI layer. It composes the LangChain
    pipeline (prompt | llm | parser) and exposes a single entry point,
    `analyze(text) -> NoteAnalysis`, that the note service calls to obtain a
    category and priority for a note.

    Responsibility boundary:
        Turns raw note text into a validated `NoteAnalysis` and GUARANTEES
        it never raises. It wires together the other AI modules (schemas,
        prompts, llm) but contains no prompt text of its own and no database
        code.

    Reliability contract (project Feature 8):
        If anything goes wrong — network error, timeout, rate limit, or the
        model returning unusable output — the failure is logged and a safe
        fallback (`category="Other"`, `priority="Medium"`) is returned. The
        application's CRUD must keep working even when the LLM does not.

    How it interacts with the rest of the app:
        `note_service` receives a `NoteCategorizer` (via `get_categorizer()`)
        and calls `analyze()` during create/update, then persists the
        returned category/priority strings.
"""

import logging
from functools import lru_cache

from langchain_core.output_parsers import PydanticOutputParser

from app.ai.llm import get_llm
from app.ai.prompts import build_categorization_prompt
from app.ai.schemas import NoteAnalysis

# Dedicated logger so AI failures are easy to filter; reuses the logging
# configuration set up in main.py.
logger = logging.getLogger("ai_smart_notes.ai")

# Classification does not need the entire note body; cap the input to bound
# token cost and latency on very long notes.
MAX_INPUT_CHARS = 4000


class NoteCategorizer:
    """Analyzes note text into a validated category + priority.

    Builds the parser, prompt, and runnable chain once on construction so
    repeated `analyze` calls reuse them.
    """

    def __init__(self) -> None:
        # The parser both (a) generates the JSON format instructions for the
        # prompt and (b) validates/parses the model output into NoteAnalysis.
        self._parser = PydanticOutputParser(pydantic_object=NoteAnalysis)
        prompt = build_categorization_prompt(self._parser.get_format_instructions())
        # The Runnable pipeline: render prompt -> call OpenRouter -> parse.
        self._chain = prompt | get_llm() | self._parser

    def analyze(self, text: str) -> NoteAnalysis:
        """Return a NoteAnalysis for the given text; never raises.

        Steps:
            1. Guard empty/whitespace input -> fallback (no LLM call).
            2. Truncate overly long input to bound cost.
            3. Invoke the chain; the parser returns a validated NoteAnalysis
               (invalid category/priority already coerced to Other/Medium).
            4. On ANY exception, log and return the safe fallback.
        """
        if not text or not text.strip():
            return NoteAnalysis.fallback()

        note_text = text.strip()[:MAX_INPUT_CHARS]

        try:
            # PydanticOutputParser returns a NoteAnalysis instance directly.
            return self._chain.invoke({"note_text": note_text})
        except Exception as exc:  # noqa: BLE001 — intentional catch-all
            # Feature 8: never crash the request because of the LLM. Log the
            # full error for diagnosis and degrade to safe defaults.
            logger.warning(
                "AI note analysis failed; falling back to Other/Medium. error=%s",
                exc,
                exc_info=True,
            )
            return NoteAnalysis.fallback()


@lru_cache
def get_categorizer() -> NoteCategorizer:
    """Build (once) and return a shared NoteCategorizer.

    Lazy + cached: the categorizer (and its LLM client) is constructed on
    first use, so importing this module never requires an API key. Tests can
    call `get_categorizer.cache_clear()` or inject their own instance.
    """
    return NoteCategorizer()
