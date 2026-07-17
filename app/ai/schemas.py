"""app/ai/schemas.py

Why this file exists:
    The structured-output contract for the AI layer. It defines the exact
    shape the LLM must return — the legal Category and Priority values and
    the `NoteAnalysis` object that a PydanticOutputParser validates the
    model's JSON against. This is what makes "the AI returns a category and
    a priority" an enforceable contract rather than a hope.

    Responsibility boundary:
        * Defines enums + a Pydantic output model only.
        * It is the SOURCE OF TRUTH for valid category/priority values.
          The Note ORM model stores these as plain strings; this layer
          guarantees (via coercion below) that only legal values are ever
          produced, so the database only ever stores valid data.
        * Knows nothing about the LLM client, prompts, or the database.

    How it interacts with the rest of the app:
        * `prompts.py` asks the parser built from `NoteAnalysis` for format
          instructions to embed in the prompt.
        * `categorizer.py` parses the LLM output into a `NoteAnalysis` and,
          on any failure, falls back to `NoteAnalysis.fallback()`.
"""

from __future__ import annotations

import enum
from typing import TypeVar

from pydantic import BaseModel, Field, field_validator


class Category(str, enum.Enum):
    """The eleven allowed note categories. `Other` is the catch-all used
    whenever the model is unsure or returns an unrecognized value."""

    WORK = "Work"
    STUDY = "Study"
    PERSONAL = "Personal"
    SHOPPING = "Shopping"
    FINANCE = "Finance"
    HEALTH = "Health"
    IDEAS = "Ideas"
    CODING = "Coding"
    MEETINGS = "Meetings"
    TRAVEL = "Travel"
    OTHER = "Other"


class Priority(str, enum.Enum):
    """The three allowed priorities. `Medium` is the safe default."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


_EnumT = TypeVar("_EnumT", bound=enum.Enum)


def _match_enum(value: object, enum_cls: type[_EnumT], default: _EnumT) -> _EnumT:
    """Best-effort map an arbitrary value onto an enum member.

    Returns the matching member (case-insensitive on its value), or
    `default` if the value is missing/unrecognized. This is the mechanism
    that turns an invalid LLM answer into a safe fallback instead of an
    error — e.g. "programming" -> default, "coding" -> Category.CODING.
    """
    if isinstance(value, enum_cls):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    for member in enum_cls:
        if member.value.lower() == text:
            return member
    return default


class NoteAnalysis(BaseModel):
    """The validated result of analyzing a note's text.

    This is the object the LLM must produce (as JSON) and the parser
    validates. The `mode="before"` validators coerce any invalid/oddly
    cased value to the safe default rather than raising, implementing the
    rule "invalid category -> Other, invalid priority -> Medium" at the
    field level — so a partially-bad response keeps its good field.
    """

    category: Category = Field(
        description=(
            "Exactly one category for the note. Must be one of: Work, Study, "
            "Personal, Shopping, Finance, Health, Ideas, Coding, Meetings, "
            "Travel, Other. Use 'Other' if none clearly fits."
        ),
    )
    priority: Priority = Field(
        description=(
            "The note's priority. Must be one of: High, Medium, Low. "
            "Use 'High' for urgent/time-sensitive items, 'Low' for casual "
            "ones, otherwise 'Medium'."
        ),
    )

    @field_validator("category", mode="before")
    @classmethod
    def _coerce_category(cls, value: object) -> Category:
        """Coerce any unrecognized category to Other (never raise)."""
        return _match_enum(value, Category, Category.OTHER)

    @field_validator("priority", mode="before")
    @classmethod
    def _coerce_priority(cls, value: object) -> Priority:
        """Coerce any unrecognized priority to Medium (never raise)."""
        return _match_enum(value, Priority, Priority.MEDIUM)

    @classmethod
    def fallback(cls) -> NoteAnalysis:
        """The canonical safe default used when the LLM cannot be reached
        or its output is unusable: category 'Other', priority 'Medium'."""
        return cls(category=Category.OTHER, priority=Priority.MEDIUM)
