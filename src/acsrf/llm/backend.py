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

    def generate(self, prompt: str, *, system: str = "") -> str:
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

