"""app/services/auth_service.py

Why this file exists:
    The business/use-case layer for authentication (Phase 6). It orchestrates
    registration and login between the router (HTTP) and the user repository
    (SQL), and composes the crypto primitives from app.core.security — all
    WITHOUT importing FastAPI, so it stays reusable and unit-testable.

    What it owns:
        * Email normalization (lowercase) so accounts are case-insensitive.
        * Duplicate-account rejection (409) and credential checking (401, with a
          message that never reveals whether an email is registered).
        * Password hashing on register, verification on login.
        * The "first account inherits existing data" rule: the very first user
          to register claims every pre-auth note/task.
        * Issuing a signed JWT for an authenticated user.

    It does NOT map HTTP status codes (it raises AppError subclasses that main.py
    translates) or read the environment (config flows through security.py).
"""

import logging

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import Token, UserLogin, UserRegister
from app.utils.exceptions import ConflictError, UnauthorizedError

logger = logging.getLogger("ai_smart_notes.auth")


class AuthService:
    """Use-case logic for registration and login."""

    def __init__(self, repository: UserRepository) -> None:
        """Inject the repository to decouple the service from storage."""
        self._repository = repository

    @staticmethod
    def _normalize_email(email: str) -> str:
        """Lowercase + trim so 'You@Example.com ' and 'you@example.com' are the
        same account on both registration and lookup."""
        return email.strip().lower()

    def register(self, data: UserRegister) -> User:
        """Create a new account and return the persisted user.

        Steps: normalize email -> reject if it already exists (409) -> hash the
        password -> persist. If this is the FIRST account, it inherits every
        owner-less note/task (the pre-auth data). Raises ConflictError on a
        duplicate email.
        """
        email = self._normalize_email(data.email)
        if self._repository.get_by_email(email) is not None:
            raise ConflictError("An account with this email already exists.")

        # Detect the first registration BEFORE inserting, so exactly one user
        # ever claims the pre-auth content.
        is_first_user = self._repository.count() == 0

        user = self._repository.create(
            User(email=email, hashed_password=hash_password(data.password))
        )

        if is_first_user:
            notes, tasks = self._repository.claim_unowned_content(user.id)
            logger.info(
                "First account %s claimed %d pre-auth note(s) and %d task(s)",
                user.id,
                notes,
                tasks,
            )

        return user

    def authenticate(self, data: UserLogin) -> User:
        """Return the user for valid credentials, else raise UnauthorizedError.

        Uses the SAME error whether the email is unknown or the password is
        wrong, so the API never reveals which emails are registered.
        """
        email = self._normalize_email(data.email)
        user = self._repository.get_by_email(email)
        if user is None or not verify_password(data.password, user.hashed_password):
            raise UnauthorizedError("Incorrect email or password.")
        return user

    @staticmethod
    def issue_token(user: User) -> Token:
        """Mint a signed JWT bearer token identifying `user`."""
        return Token(access_token=create_access_token(str(user.id)))
