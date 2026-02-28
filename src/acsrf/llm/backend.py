"""Abstract LLM backend with concrete Gemini implementation.

Designed so that a local model (Ollama / vLLM) can be swapped in later
by implementing the same ``LLMBackend`` protocol.
"""
from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from google import genai
from google.genai import types


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------
@runtime_checkable
class LLMBackend(Protocol):
    """Minimal contract every LLM backend must satisfy."""

    def generate(self, prompt: str, *, system: str = "") -> str:
        """Return the model's text response given a user prompt and optional system instruction."""
        ...


# ---------------------------------------------------------------------------
# Gemini implementation (google-genai SDK)
# ---------------------------------------------------------------------------
class GeminiBackend:
    """Google Gemini API backend using the ``google-genai`` SDK."""

    def __init__(self, model_name: str = "gemini-2.5-flash", api_key: str | None = None):
        key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not key:
            raise ValueError(
                "GEMINI_API_KEY not set. Pass it explicitly or add it to your .env file."
            )
        self._client = genai.Client(api_key=key)
        self._model_name = model_name
        self._cached_content_name: str | None = None

    # ----- Context caching ------------------------------------------------
    def cache_context(self, system_instruction: str, display_name: str = "acsrf-schema-cache") -> None:
        """Create a server-side context cache for repeated prompt components.

        Cached tokens are billed at ~75% less and skip re-processing.
        Call this once at pipeline startup with the schema + system prompt.
        """
        try:
            cache = self._client.caches.create(
                model=self._model_name,
                config=types.CreateCachedContentConfig(
                    display_name=display_name,
                    system_instruction=system_instruction,
                    contents=["You are a cloud security analysis assistant."],
                ),
            )
            self._cached_content_name = cache.name
        except Exception:
            # Caching is best-effort; fall back to regular calls if unsupported
            self._cached_content_name = None

    # ----- Generation -----------------------------------------------------
    def generate(self, prompt: str, *, system: str = "") -> str:
        if self._cached_content_name and not system:
            # Use cached context (system instruction is baked into the cache)
            config = types.GenerateContentConfig(
                cached_content=self._cached_content_name,
            )
        else:
            config = types.GenerateContentConfig(
                system_instruction=system or None,
            )
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=config,
        )
        return response.text


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
_BACKENDS = {
    "gemini": GeminiBackend,
}


def get_llm_backend(backend_name: str | None = None, **kwargs) -> LLMBackend:
    """Instantiate the requested backend (defaults to env var ``LLM_BACKEND``)."""
    name = (backend_name or os.environ.get("LLM_BACKEND", "gemini")).lower()
    cls = _BACKENDS.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown LLM backend '{name}'. Available: {list(_BACKENDS.keys())}"
        )
    return cls(**kwargs)

