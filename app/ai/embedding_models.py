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
        * VectorMetadata — the note fields carried alongside a search hit
          (Feature 2). Timestamps are ISO-8601 strings so the shape is a clean,
          JSON-friendly value the search API can pass straight through.
        * SearchResult — one ranked hit returned by /search (Feature 4),
          carrying the full metadata plus the note content and a
          similarity_score percentage.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class VectorMetadata(BaseModel):
    """The note fields carried by a single vector-search hit.

    Timestamps are kept as ISO-8601 strings rather than datetimes, giving a
    flat, JSON-friendly shape. vector_store.query builds this from a JOIN to the
    `notes` table, so the values always reflect the note's current state.
    """

    note_id: int = Field(description="Primary key of the note in PostgreSQL.")
    title: str = Field(description="Note title.")
    category: str = Field(description="AI-assigned category.")
    priority: str = Field(description="AI-assigned priority.")
    created_at: str = Field(description="Note creation timestamp (ISO-8601).")
    updated_at: str = Field(description="Note last-update timestamp (ISO-8601).")


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
        """Assemble a SearchResult from a single vector-store hit.

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
