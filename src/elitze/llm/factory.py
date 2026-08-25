"""LLM factory: choose NIM (if key) or the deterministic offline planner."""

from __future__ import annotations

from ..config import Settings
from ..log import get_logger
from .base import LLM
from .dry import DryLLM
from .nim import NimLLM

log = get_logger("llm.factory")


def get_llm(settings: Settings) -> LLM:
    backend = settings.llm_backend
    has_key = settings.nim_api_key_plain() is not None
    if backend == "nim":
        return NimLLM(settings)
    if backend == "dry":
        return DryLLM()
    # auto
    if has_key:
        try:
            return NimLLM(settings)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("NIM init failed, falling back to dry", fields={"error": str(exc)})
            return DryLLM()
    log.info("no NIM key configured; using deterministic offline planner")
    return DryLLM()
