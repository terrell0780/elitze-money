"""Model inference layer (NVIDIA NIM) with a deterministic offline fallback."""

from __future__ import annotations

from .base import LLM, ChatMessage
from .factory import get_llm

__all__ = ["LLM", "ChatMessage", "get_llm"]
