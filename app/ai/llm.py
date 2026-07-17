"""app/ai/llm.py

Why this file exists:
    The LLM client factory — the ONLY module that knows we are specifically
    talking to OpenRouter. It builds a configured ChatOpenAI instance from
    our typed Settings and hands it to the categorizer.

    Responsibility boundary:
        Client construction only. It does not define prompts, parse output,
        or contain business logic. Because OpenRouter speaks the OpenAI
        API, we use the standard ChatOpenAI client and simply override its
        base_url — so swapping providers later means editing just this file.

    How it interacts with the rest of the app:
        `categorizer.py` calls `get_llm()` and pipes it between the prompt
        and the parser (`prompt | llm | parser`). All configuration flows
        from `app.core.config.Settings`; nothing here reads os.environ.
"""

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.config import get_settings


@lru_cache
def get_llm() -> ChatOpenAI:
    """Build (once) and return the OpenRouter-backed chat client.

    Why a cached factory:
        * Lazy — the client is created on first use, so merely importing
          this module never requires an API key (keeps imports/tests cheap).
        * Single construction point — connection setup happens once and the
          instance is reused, matching the `get_settings()` pattern.
        * Overridable — tests can call `get_llm.cache_clear()` to rebuild
          with different settings, or patch this function wholesale.
    """
    settings = get_settings()
    return ChatOpenAI(
        # OpenRouter model slug, e.g. "openai/gpt-4o-mini".
        model=settings.openrouter_model,
        # Credentials + endpoint that make this client talk to OpenRouter
        # instead of OpenAI directly.
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        # Deterministic output for classification.
        temperature=settings.llm_temperature,
        # Bound each call so a hung request cannot stall the API; the
        # categorizer falls back to safe defaults on timeout.
        timeout=settings.llm_timeout,
        # Retry a couple of transient errors, but stay bounded so failures
        # surface quickly to the fallback path.
        max_retries=2,
        # Optional OpenRouter attribution headers (used by its dashboard /
        # model rankings). Harmless if unused.
        default_headers={"X-Title": settings.app_name},
    )
