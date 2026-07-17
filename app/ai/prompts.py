"""app/ai/prompts.py

Why this file exists:
    The single home for the LLM prompt text. Per project rules, prompts are
    NOT hardcoded inside logic functions — the instructions live here as
    module-level constants, and a thin builder assembles them into a
    LangChain ChatPromptTemplate. Tuning the prompt never requires touching
    the client (`llm.py`) or the orchestration (`categorizer.py`).

    Responsibility boundary:
        Defines WHAT we say to the model only. It does not call the model,
        parse output, or know about the database.

    How it interacts with the rest of the app:
        `categorizer.py` builds a PydanticOutputParser from `NoteAnalysis`,
        passes its `format_instructions` into `build_categorization_prompt`,
        and pipes the resulting prompt into the LLM and parser.

    Note on braces: literal JSON braces in the few-shot examples are escaped
    as `{{` / `}}` so ChatPromptTemplate does not treat them as template
    variables. The only real template variables are `{format_instructions}`
    (filled once via .partial) and `{note_text}` (filled per request).
"""

from langchain_core.prompts import ChatPromptTemplate

# The system message: role, rules, allowed values, examples, and a slot for
# the parser's format instructions. Stable across requests.
SYSTEM_PROMPT = """You are a precise note-classification assistant. Given the \
text of a single note, you assign exactly one category and one priority.

Allowed categories (choose exactly one):
Work, Study, Personal, Shopping, Finance, Health, Ideas, Coding, Meetings, \
Travel, Other.
If no category clearly fits, use "Other".

Allowed priorities (choose exactly one):
- High: urgent or time-sensitive (deadlines, appointments, "tonight", "today").
- Medium: normal tasks with no explicit urgency.
- Low: casual, optional, or leisure items.
If unsure, use "Medium".

Rules:
- Respond with a single JSON object ONLY. No prose, no explanations, no \
markdown code fences.
- Use only the allowed values, spelled exactly as shown.

Examples:
Note: "Submit assignment tonight"
{{"category": "Study", "priority": "High"}}

Note: "Buy milk and vegetables"
{{"category": "Shopping", "priority": "Medium"}}

Note: "Watch a movie this weekend"
{{"category": "Personal", "priority": "Low"}}

Note: "Learn LangChain and build a RAG pipeline"
{{"category": "Coding", "priority": "Medium"}}

{format_instructions}"""

# The human message: carries only the note's text for this request.
HUMAN_PROMPT = 'Note: "{note_text}"'


def build_categorization_prompt(format_instructions: str) -> ChatPromptTemplate:
    """Assemble the categorization prompt with the parser's format
    instructions baked in.

    `format_instructions` (from PydanticOutputParser) is filled once via
    `.partial`, leaving only `note_text` to be supplied per request. The
    actual prompt wording stays in the module-level constants above.
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_PROMPT),
        ]
    )
    return prompt.partial(format_instructions=format_instructions)


# --- Task extraction (suggest tasks from a note) ---------------------
# Same shape as categorization: a system prompt with rules + escaped-brace
# few-shot examples and a {format_instructions} slot, plus a human message
# carrying only {note_text}. The examples teach the model to (a) return ONLY
# actionable to-dos, and (b) return an empty list when a note is not actionable.
TASK_EXTRACTION_SYSTEM_PROMPT = """You extract concrete, actionable to-do tasks \
from a personal note.

Rules:
- Return ONLY items that are something to DO — a concrete action the writer \
needs to take.
- Ignore ideas, opinions, facts, feelings, and anything already done.
- Each task has a short imperative title (start with a verb) and an optional \
one-line description carrying any useful detail from the note (deadline, who, \
where). Use null for the description when there is nothing to add.
- If the note contains no actionable tasks, return an empty list.
- Respond with a single JSON object ONLY. No prose, no explanations, no \
markdown code fences.

Examples:
Note: "Meeting with Sarah went well. Need to send her the report and book a \
follow-up for next week."
{{"tasks": [{{"title": "Send Sarah the report", "description": null}}, \
{{"title": "Book a follow-up meeting with Sarah", "description": "For next week"}}]}}

Note: "Some thoughts about a new app idea that uses AI to suggest recipes."
{{"tasks": []}}

Note: "Groceries: milk and eggs. Also pay the electricity bill before Friday."
{{"tasks": [{{"title": "Buy groceries", "description": "Milk and eggs"}}, \
{{"title": "Pay the electricity bill", "description": "Before Friday"}}]}}

{format_instructions}"""

TASK_EXTRACTION_HUMAN_PROMPT = 'Note: "{note_text}"'


def build_task_extraction_prompt(format_instructions: str) -> ChatPromptTemplate:
    """Assemble the task-extraction prompt with the parser's format
    instructions baked in.

    Mirrors build_categorization_prompt: `format_instructions` (from the
    TaskSuggestionList parser) is filled once via `.partial`, leaving only
    `note_text` per request.
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", TASK_EXTRACTION_SYSTEM_PROMPT),
            ("human", TASK_EXTRACTION_HUMAN_PROMPT),
        ]
    )
    return prompt.partial(format_instructions=format_instructions)
