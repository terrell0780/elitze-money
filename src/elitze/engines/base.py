"""Revenue engine base classes and registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..domain.enums import EngineType
from ..domain.errors import EngineNotFoundError
from ..domain.models import BudgetAllocation, ExecutionAction, ExecutionResult


@dataclass
class EngineContext:
    """Everything an engine may need to plan/execute, injected by the loop."""

    settings: Any
    llm: Any
    policy: Any
    repository: Any
    ledger: Any
    vault: Any
    budget: BudgetAllocation | None = None
    experiment_id: str | None = None
    strategy_id: str | None = None


class RevenueEngine(Protocol):
    """Interface all engines implement."""

    engine_type: EngineType

    def plan(self, ctx: EngineContext, thesis: str) -> list[ExecutionAction]: ...

    def execute(self, ctx: EngineContext, actions: list[ExecutionAction]) -> ExecutionResult: ...


class EngineRegistry:
    def __init__(self) -> None:
        self._engines: dict[EngineType, type[RevenueEngine]] = {}

    def register(self, cls: type[RevenueEngine]) -> type[RevenueEngine]:
        self._engines[cls.engine_type] = cls
        return cls

    def get(self, engine: EngineType) -> RevenueEngine:
        try:
            cls = self._engines[engine]
        except KeyError:
            raise EngineNotFoundError(f"no engine registered for {engine.value}") from None
        # Instantiate; if it needs constructor deps, they must be default-free.
        try:
            return cls()
        except TypeError:
            return cls  # type: ignore[return-value]

    def available(self) -> list[EngineType]:
        return list(self._engines.keys())


registry = EngineRegistry()
