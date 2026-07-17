"""app/ai/embedding_models.py

Why this file exists:
    The shared vocabulary of the embedding domain — pure Pydantic DTOs that
    travel between the vector store and the search engine. Defining these
    shapes once lets every vector module agree on them without coupling to
    one another's implementation.

    Responsibility boundary:
        Data contracts only. This is a LEAF module: it imports no Chroma, no
        database, and no sentence-transformers code, so it stays dependency
        free and safe to import anywhere.

    Two models live here:
        * VectorMetadata — the metadata attached to each stored vector
          (Feature 2), shaped to satisfy Chroma's primitive-only metadata
          rule (str / int / float / bool — so timestamps are ISO strings).
        * SearchResult — one ranked hit returned by /search (Feature 4),
          carrying the full metadata plus the note content and a
          similarity_score percentage.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class VectorMetadata(BaseModel):
    """Metadata stored alongside a note's vector in ChromaDB.

    Chroma metadata values must be primitives (str/int/float/bool), so the
    timestamps are kept as ISO-8601 strings rather than datetimes. The
    note-aware construction of this object (from a Note ORM instance) lives
    in note_embedding_service, NOT here, to keep this module pure.
    """

    note_id: int = Field(description="Primary key of the note in PostgreSQL.")
    title: str = Field(description="Note title at index time.")
    category: str = Field(description="AI-assigned category at index time.")
    priority: str = Field(description="AI-assigned priority at index time.")
    created_at: str = Field(description="Note creation timestamp (ISO-8601).")
    updated_at: str = Field(description="Note last-update timestamp (ISO-8601).")

    def to_chroma(self) -> dict[str, str | int]:
        """Serialize to a Chroma-safe metadata dict (primitives only).

        `model_dump()` yields note_id as int and the rest as str — all
        accepted by Chroma. Centralizing this here means the
        primitives-only constraint is handled in exactly one place.
        """
        return self.model_dump()

    @classmethod
    def from_chroma(cls, raw: dict[str, object]) -> VectorMetadata:
        """Rebuild a typed VectorMetadata from a raw Chroma metadata dict
        returned by a query. Pydantic coerces the primitive values back
        into the declared field types."""
        return cls.model_validate(raw)


class SearchResult(BaseModel):
    """One ranked semantic-search hit returned by the /search endpoint.

    Combines the note's metadata (Feature 2) with its content and a
    similarity score expressed as an integer percentage (Feature 4).
    """

    note_id: int = Field(description="Primary key of the matched note.")
    title: str = Field(description="Note title.")
    content: str | None = Field(default=None, description="Note body text.")
    category: str = Field(description="AI-assigned category.")
    priority: str = Field(description="AI-assigned priority.")
    created_at: str = Field(description="Note creation timestamp (ISO-8601).")
    updated_at: str = Field(description="Note last-update timestamp (ISO-8601).")
    similarity_score: int = Field(
        description="Similarity to the query, as a percentage 0-100 (higher is closer).",
    )

    @classmethod
    def from_hit(
        cls,
        metadata: VectorMetadata,
        content: str | None,
        similarity_score: int,
    ) -> SearchResult:
        """Assemble a SearchResult from a single Chroma hit.

        `metadata` supplies the note fields, `content` is the stored
        document text, and `similarity_score` is the converted percentage.
        Centralizing the assembly keeps search.py free of field-mapping
        boilerplate.
        """
        return cls(
            note_id=metadata.note_id,
            title=metadata.title,
            content=content,
            category=metadata.category,
            priority=metadata.priority,
            created_at=metadata.created_at,
            updated_at=metadata.updated_at,
            similarity_score=similarity_score,
        )
