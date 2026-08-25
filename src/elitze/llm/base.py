"""LLM abstraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ChatResult:
    content: str
    raw: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)


class LLM(Protocol):
    def chat(self, messages: list[ChatMessage], **kwargs: Any) -> ChatResult: ...

    @property
    def backend_name(self) -> str: ...
