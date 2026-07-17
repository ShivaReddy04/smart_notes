"""app/api/deps.py

Why this file exists:
    Shared FastAPI dependencies for the API layer. Currently the auth guard:
    `get_current_user` turns an incoming `Authorization: Bearer <token>` header
    into the authenticated `User`, or fails with a uniform 401. Every protected
    route declares `Depends(get_current_user)`, so authentication is enforced in
    ONE place and each route simply receives the current user.

    Responsibility boundary:
        Wiring only — extract the token, verify it (app.core.security), load the
        user (UserRepository), and raise UnauthorizedError on any problem. No
        business logic; no HTTP-status mapping (main.py maps AppError -> JSON).

    Why HTTPBearer(auto_error=False):
        With auto_error=True FastAPI would short-circuit a MISSING header with
        its own 403 before our code runs. Setting it False lets us treat every
        failure — missing, malformed, expired, unknown user — as the SAME 401
        through our AppError handler, so clients get one consistent shape.
"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.utils.exceptions import UnauthorizedError

# Declares the bearer scheme (adds the Authorize button in the docs) but does
# not auto-reject; we raise our own UnauthorizedError instead.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the bearer token, or raise 401.

    Steps: require an Authorization header -> decode + verify the JWT -> parse
    its subject as the user id -> load that user. ANY failure (missing header,
    bad/expired token, non-numeric subject, deleted account) becomes a single
    401 UnauthorizedError, so the API never leaks which step failed.
    """
    if credentials is None:
        raise UnauthorizedError("Not authenticated.")

    subject = decode_access_token(credentials.credentials)
    if subject is None:
        raise UnauthorizedError("Invalid or expired token.")

    try:
        user_id = int(subject)
    except ValueError:
        raise UnauthorizedError("Invalid token subject.")

    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        # Token was valid but the account is gone (deleted) — treat as unauth.
        raise UnauthorizedError("Account no longer exists.")

    return user
