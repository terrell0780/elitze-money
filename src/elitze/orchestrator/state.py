"""Orchestrator state (typed).

``LoopState`` is the accumulated state threaded through every node of the
LangGraph. The ``experiment`` field is a plain dict (the JSON-serializable
Experiment) because LangGraph state must be JSON-safe for checkpointing.
"""

from __future__ import annotations

from typing import Any, TypedDict


class LoopState(TypedDict, total=False):
    experiment_id: str
    experiment: dict[str, Any]
    candidates: list[dict[str, Any]]
    model: dict[str, Any]
    budget: dict[str, Any]
    execution: dict[str, Any]
    measurement: dict[str, Any]
    evaluation: dict[str, Any]
    improvement: dict[str, Any]
    decision: dict[str, Any]
    errors: list[str]
    notes: list[str]
    iteration: int
    max_iterations: int
    promote: bool
    kill: bool
    reinvest: bool
    budget_approved: bool
    simulated: bool
