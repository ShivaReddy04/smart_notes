"""app/schemas/user.py

Why this file exists:
    Defines the API contract for authentication (Phase 6) — the Pydantic models
    that validate register/login request JSON and shape the responses. Same role
    and boundary as the other schema files: validation at the HTTP edge, nothing
    about storage, hashing, or tokens.

    Two security-relevant rules live here:
        * The password has a minimum length (registration only) and a maximum
          that matches bcrypt's 72-byte limit, so what the user types is exactly
          what gets hashed (see app/core/security.py).
        * `UserResponse` deliberately has NO password field of any kind, so a
          hash can never leak through the API.

    How it interacts with the rest of the app:
        * The auth router uses these as request bodies / response_model.
        * The auth service receives validated Register/Login objects.
        * `UserResponse` is built from an ORM `User` via from_attributes.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# bcrypt hashes at most 72 bytes; cap the password there so validation and the
# hasher agree on the effective length. Mirrors _BCRYPT_MAX_BYTES in security.py.
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 72


class UserRegister(BaseModel):
    """Request body for POST /auth/register.

    `str_strip_whitespace` trims the email; the password is intentionally NOT
    stripped (leading/trailing spaces can be legitimate password characters).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr = Field(
        description="Account email (also the login identifier).",
        examples=["you@example.com"],
    )
    # Enforced only on registration, so we never leak the policy on login.
    password: str = Field(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description=f"Password ({PASSWORD_MIN_LENGTH}-{PASSWORD_MAX_LENGTH} characters).",
        examples=["a-strong-passphrase"],
    )


class UserLogin(BaseModel):
    """Request body for POST /auth/login.

    No length constraints on the password here: login just checks the supplied
    value against the stored hash, and echoing the registration policy on a
    failed login would leak it.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr = Field(description="Account email.")
    password: str = Field(description="Account password.")


class UserResponse(BaseModel):
    """Public shape of a user — everything safe to return, and nothing else.

    `from_attributes=True` lets Pydantic build this straight from an ORM `User`
    (`UserResponse.model_validate(user)`). There is no password/hash field, so
    the secret can never be serialized out.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Server-assigned unique identifier.")
    email: EmailStr = Field(description="Account email.")
    created_at: datetime = Field(description="When the account was created (UTC-aware).")


class Token(BaseModel):
    """Response body for a successful register/login — the JWT to send back.

    The client stores `access_token` and sends it on every request as
    `Authorization: Bearer <access_token>`. `token_type` is always "bearer"
    (the OAuth2 convention many HTTP clients expect).
    """

    access_token: str = Field(description="Signed JWT access token.")
    token_type: str = Field(default="bearer", description="Always 'bearer'.")
