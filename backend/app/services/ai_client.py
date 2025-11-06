"""Client helper to interact with Gemma 2 served by Ollama."""
from __future__ import annotations

from typing import Iterable

import httpx

from ..core.config import get_settings


class GemmaClient:
    """Minimal asynchronous client for talking to a local Ollama instance."""

    def __init__(self, *, timeout: float = 30.0) -> None:
        settings = get_settings()
        self._base_url = settings.ollama_url.rstrip("/")
        self._model = settings.ollama_model
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        """Close the underlying HTTP connection pool."""

        await self._client.aclose()

    async def generate_chat_reply(self, messages: Iterable[dict[str, str]]) -> str:
        """Send the full conversation history to Ollama and return the reply."""

        payload = {
            "model": self._model,
            "messages": list(messages),
            "stream": False,
        }
        response = await self._client.post(
            f"{self._base_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "")

    async def generate_action(self, prompt: str) -> str:
        """Ask Gemma 2 to suggest an action based on a prompt."""

        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        response = await self._client.post(
            f"{self._base_url}/api/generate",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()

    async def __aenter__(self) -> "GemmaClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()
