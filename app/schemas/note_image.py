"""app/schemas/note_image.py

Why this file exists:
    Defines the API contract for an image attached to a note — the Pydantic
    model that serializes a NoteImage ORM row into JSON. Same boundary as the
    other schema files: shape of data crossing the HTTP edge only, nothing
    about storage or business rules.

    The one interesting job here is turning the opaque on-disk `filename` into
    a URL a browser can actually load. Clients must NEVER depend on the raw
    stored filename or the disk layout; they get a ready-to-use `url` built
    from `media_url_prefix`. If we ever move images behind a CDN or change the
    mount point, only this computed field (and the setting) changes.

    How it interacts with the rest of the app:
        * The image routes declare `NoteImageResponse` as response_model.
        * It is built directly from a NoteImage ORM instance via
          `from_attributes=True`.
        * `NoteResponse` embeds a list of these, so every note carries its
          images in one payload.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.config import get_settings


class NoteImageResponse(BaseModel):
    """Response body describing one attached image."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Server-assigned unique identifier of the image.")

    # Read from the ORM row so the computed `url` below can use it, but kept
    # OUT of the JSON (`exclude=True`): the disk name is an implementation
    # detail. Clients use `url`, never this.
    filename: str = Field(exclude=True)

    original_name: str = Field(
        description="The filename as the user originally uploaded it.",
    )
    content_type: str = Field(description="MIME type, e.g. 'image/png'.")
    size: int = Field(description="Size of the stored file in bytes.")
    created_at: datetime = Field(description="When the image was uploaded (UTC-aware).")

    @computed_field(description="Public URL to fetch the image bytes.")  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        """Build the browser-usable URL from the media prefix + stored name.

        get_settings() is cached, so this is effectively free per call. The
        result looks like "/media/9f3a...c1.png"; the frontend joins it onto
        the API base to form an absolute URL.
        """
        return f"{get_settings().media_url_prefix}/{self.filename}"
