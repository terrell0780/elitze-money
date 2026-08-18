"""Deterministic offline planner.

Used when no NIM API key is configured (``ELITZE_LLM_BACKEND=dry`` or
``auto`` without a key). It never invents revenue — it only produces
structured planning/analysis text deterministically from the input.
"""

from __future__ import annotations

from typing import Any

from .base import ChatMessage, ChatResult


class DryLLM:
    @property
    def backend_name(self) -> str:
        return "dry"

    def chat(self, messages: list[ChatMessage], **kwargs: Any) -> ChatResult:
        prompt = "\n".join(f"{m.role}: {m.content}" for m in messages)
        content = (
            "DRY PLAN (deterministic offline planner, no external model):\n"
            f"- Objective derived from prompt ({len(prompt)} chars).\n"
            "- Suggest a single, budgeted, reversible experiment.\n"
            "- Prefer low-cost, measurable, real-execution channels.\n"
            "- Record assumptions and success metrics explicitly.\n"
            "- No revenue may be assumed; revenue must be measured from\n"
            "  verified external events only."
        )
        return ChatResult(content=content, usage={"tokens": 0})
