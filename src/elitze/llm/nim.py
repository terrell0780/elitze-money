"""NVIDIA NIM chat-completions client.

Calls the OpenAI-compatible NIM endpoint
(``POST {base_url}/chat/completions``). Requires ``ELITZE_NIM_API_KEY``.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..config import Settings
from ..log import get_logger
from .base import ChatMessage, ChatResult

log = get_logger("llm.nim")


class NimLLM:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.nim_model
        self._client = httpx.Client(timeout=settings.http_timeout_seconds)
        self._key = settings.nim_api_key_plain()
        if not self._key:
            raise ValueError("NIM client requires an API key")

    @property
    def backend_name(self) -> str:
        return f"nim:{self._model}"

    def chat(self, messages: list[ChatMessage], **kwargs: Any) -> ChatResult:
        url = f"{self._settings.nim_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": kwargs.get("temperature", 0.3),
            "max_tokens": kwargs.get("max_tokens", 1024),
        }
        resp = self._client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        log.info("nim chat ok", fields={"model": self._model, "usage": usage})
        return ChatResult(content=content, raw=data, usage=usage)
