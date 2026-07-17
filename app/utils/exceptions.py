"""app/utils/exceptions.py

Why this file exists:
    Gives every layer a framework-agnostic vocabulary for failure. Services
    must be able to signal "this note does not exist" or "this input is
    invalid" WITHOUT importing FastAPI — otherwise the business layer would
    be chained to the web framework and unusable from a CLI, a background
    worker, or a unit test.

    Responsibility boundary:
        Defines plain Python exceptions only. Each carries a human-readable
        message and an HTTP status *hint* (`status_code`). It does NOT know
        how to build an HTTP response — that translation happens once, in
        `main.py`, the only HTTP-aware module. This is Dependency Inversion
        applied to error handling: the service depends on this abstraction,
        not on `fastapi.HTTPException`.

    How it interacts with the rest of the app:
        * Services raise these (e.g. `raise NotFoundError("Note", note_id)`).
        * A single exception handler in `main.py` catches `AppError` and
          maps `exc.status_code` + `exc.message` to a consistent JSON body.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for all expected, application-level errors.

    Carrying `status_code` as a class attribute lets the HTTP layer map any
    subclass generically (read `exc.status_code`) instead of maintaining a
    branch per error type. Defaults to 500 so an unmapped/unexpected
    AppError surfaces as an Internal Server Error.
    """

    status_code: int = 500
    # A safe, generic default message; subclasses/instances override it.
    message: str = "An unexpected application error occurred."

    def __init__(self, message: str | None = None) -> None:
        # Allow an explicit message, otherwise fall back to the class
        # default. Passing it to super() makes str(exc) and logging useful.
        if message is not None:
            self.message = message
        super().__init__(self.message)


class NotFoundError(AppError):
    """Raised when a requested entity does not exist. Maps to HTTP 404.

    The workhorse error for CRUD reads/updates/deletes: the repository
    returns None, and the service converts that absence into this error.
    """

    status_code = 404

    def __init__(self, entity: str, identifier: object) -> None:
        """Build a clear message from the entity name and its identifier.

        Example:
            NotFoundError("Note", 5) -> "Note with id 5 was not found."
        """
        self.entity = entity
        self.identifier = identifier
        super().__init__(f"{entity} with id {identifier} was not found.")


class BadRequestError(AppError):
    """Raised when a request is syntactically valid but violates a business
    rule. Maps to HTTP 400.

    Lightly used in Phase 1 — most malformed input is rejected earlier by
    Pydantic (422). Provided for the spec's 400 case and as the home for
    future domain-rule violations.
    """

    status_code = 400
