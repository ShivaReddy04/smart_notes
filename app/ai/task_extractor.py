"""app/ai/task_extractor.py

Why this file exists:
    The orchestration for "suggest tasks from a note" — the task-extraction
    sibling of the categorizer. It composes the same LangChain pipeline shape
    (prompt | llm | parser) and exposes a single entry point,
    `extract(text) -> list[TaskSuggestion]`, that the note service calls.

    Responsibility boundary:
        Turns raw note text into a list of validated task DRAFTS and GUARANTEES
        it never raises. It wires the other AI modules (prompt, llm) and the
        TaskSuggestionList schema together but owns no prompt text and no
        database code.

    Reliability contract (mirrors the categorizer):
        Extraction is a best-effort assist, not core CRUD. Empty/whitespace
        input, a network/timeout error, or unparseable model output all yield an
        EMPTY list (logged), never an exception — a flaky suggestion must never
        500 a request or block the user.

    How it interacts with the rest of the app:
        `note_service.suggest_tasks` fetches the owner's note, calls `extract()`
        on its text, and returns the suggestions to the route. The client turns
        the chosen ones into real tasks via the normal POST /tasks.
"""

import logging
from functools import lru_cache

from langchain_core.output_parsers import PydanticOutputParser

from app.ai.llm import get_llm
from app.ai.prompts import build_task_extraction_prompt
from app.schemas.task import TaskSuggestion, TaskSuggestionList

# Reuse the AI logger namespace so extraction failures filter with the rest.
logger = logging.getLogger("ai_smart_notes.ai")

# Cap the note text handed to the model, bounding token cost/latency on very
# long notes (same guard the categorizer uses).
MAX_INPUT_CHARS = 4000


class TaskExtractor:
    """Extracts actionable task suggestions from note text.

    Builds the parser, prompt, and runnable chain once on construction so
    repeated `extract` calls reuse them.
    """

    def __init__(self) -> None:
        # The parser both generates the JSON format instructions for the prompt
        # and validates/parses the model output into a TaskSuggestionList.
        self._parser = PydanticOutputParser(pydantic_object=TaskSuggestionList)
        prompt = build_task_extraction_prompt(self._parser.get_format_instructions())
        self._chain = prompt | get_llm() | self._parser

    def extract(self, text: str) -> list[TaskSuggestion]:
        """Return suggested tasks for the given note text; never raises.

        Steps:
            1. Guard empty/whitespace input -> [] (no LLM call).
            2. Truncate overly long input to bound cost.
            3. Invoke the chain; the parser returns a validated
               TaskSuggestionList.
            4. On ANY exception, log and return [] — a failed extraction simply
               yields no suggestions.
        """
        if not text or not text.strip():
            return []

        note_text = text.strip()[:MAX_INPUT_CHARS]

        try:
            result = self._chain.invoke({"note_text": note_text})
            return result.tasks
        except Exception as exc:  # noqa: BLE001 — intentional catch-all
            logger.warning(
                "Task extraction failed; returning no suggestions. error=%s",
                exc,
                exc_info=True,
            )
            return []


@lru_cache
def get_task_extractor() -> TaskExtractor:
    """Build (once) and return a shared TaskExtractor.

    Lazy + cached like get_categorizer(): the extractor (and its LLM client) is
    constructed on first use, so importing this module never requires an API
    key. Tests can call `get_task_extractor.cache_clear()` or inject their own.
    """
    return TaskExtractor()
