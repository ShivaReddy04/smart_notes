"""app/api/routes/auth.py

Why this file exists:
    The HTTP boundary for authentication (Phase 6). Like the other routers it
    only translates requests into service calls and shapes responses — no
    hashing, no SQL, no token logic (all of that lives in AuthService +
    app.core.security). It also owns the auth dependency wiring
    (`get_auth_service`: get_db -> UserRepository -> AuthService).

    Endpoints:
        * POST /auth/register -> create an account, return a token (the client
          is logged in immediately, so there is no separate login round-trip).
        * POST /auth/login    -> exchange email+password for a token.
        * GET  /auth/me       -> the current user; the first route protected by
          get_current_user, used by the frontend to restore a session on load.

    How it interacts with the rest of the app:
        * main.py includes this router under the global API prefix.
        * A duplicate email (409) or bad credentials (401) is raised by the
          service as an AppError and mapped to JSON by main.py's handler.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import Token, UserLogin, UserRegister, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Assemble a request-scoped AuthService (get_db -> repo -> service)."""
    return AuthService(UserRepository(db))


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account and receive an access token",
)
def register(
    payload: UserRegister,
    service: AuthService = Depends(get_auth_service),
) -> Token:
    """Register a new account and return a bearer token (auto-login).

    The email must be unique (409 otherwise). The FIRST account to register
    inherits any notes/tasks that existed before auth. On success the client
    stores the returned token and is immediately authenticated.
    """
    user = service.register(payload)
    return service.issue_token(user)


@router.post(
    "/login",
    response_model=Token,
    summary="Exchange email + password for an access token",
)
def login(
    payload: UserLogin,
    service: AuthService = Depends(get_auth_service),
) -> Token:
    """Verify credentials and return a bearer token, or 401 on failure."""
    user = service.authenticate(payload)
    return service.issue_token(user)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the currently authenticated user",
)
def read_me(current_user: User = Depends(get_current_user)) -> User:
    """Return the account behind the supplied bearer token.

    Protected by get_current_user, so a missing/invalid token yields 401. The
    frontend calls this on load to confirm a stored token is still valid and to
    show who is signed in.
    """
    return current_user