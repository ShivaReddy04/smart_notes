"""app/core/security.py

Why this file exists:
    The single home for the low-level auth primitives (Phase 6): hashing and
    verifying passwords, and creating and decoding JWT access tokens. Isolating
    them here means the rest of the app depends on four small, testable
    functions and never touches bcrypt or PyJWT directly — the same "one place
    does the sensitive thing" discipline used for the DB and LLM clients.

    Responsibility boundary:
        Pure crypto helpers only. No database access, no request handling, no
        knowledge of users beyond an opaque `subject` string. The auth service
        and the get_current_user dependency compose these.

    All configuration (the signing secret, algorithm, token lifetime) flows from
    app.core.config.Settings; nothing here reads os.environ.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

# bcrypt hashes at most the first 72 BYTES of a password (and bcrypt 4+/5 raises
# on longer input). We truncate to 72 bytes in BOTH hash and verify so the two
# always agree; the register schema also caps password length to match.
_BCRYPT_MAX_BYTES = 72


def _encode(password: str) -> bytes:
    """UTF-8 encode and truncate a password to bcrypt's 72-byte limit."""
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash of `password`, safe to persist."""
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Return True iff `password` matches the stored bcrypt `hashed` value.

    Any malformed/legacy hash string is treated as a non-match rather than an
    error, so a bad row can never crash login.
    """
    try:
        return bcrypt.checkpw(_encode(password), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    """Create a signed JWT whose `sub` claim identifies the user.

    `subject` is the user id as a string (the JWT `sub` claim must be a string).
    The token carries issued-at (`iat`) and expiry (`exp`) claims and is signed
    with the configured secret + algorithm. `expires_minutes` overrides the
    configured lifetime when given (used by tests).
    """
    settings = get_settings()
    minutes = (
        expires_minutes
        if expires_minutes is not None
        else settings.access_token_expire_minutes
    )
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Verify a JWT and return its subject (user id string), or None if invalid.

    Returns None on ANY problem — bad signature, expired token, malformed
    string, or a missing/non-string subject — so callers get a single, safe
    "not authenticated" signal instead of a grab-bag of exceptions.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) else None
