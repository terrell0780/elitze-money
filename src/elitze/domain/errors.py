"""Domain exceptions."""

from __future__ import annotations


class ElitzeError(Exception):
    """Base error for the Elitze Money Engine."""


class PolicyDeniedError(ElitzeError):
    """A policy guardrail blocked an action."""

    def __init__(self, rule: str, detail: str) -> None:
        self.rule = rule
        self.detail = detail
        super().__init__(f"[{rule}] {detail}")


class BudgetExceededError(ElitzeError):
    """An action would exceed an allocated budget."""


class InsufficientFundsError(ElitzeError):
    """The reinvestment pool has insufficient funds."""


class InvalidStateError(ElitzeError):
    """An operation was attempted in an invalid state."""


class EngineNotFoundError(ElitzeError):
    """An unknown revenue engine was requested."""


class RevenueVerificationError(ElitzeError):
    """A revenue event could not be verified and was rejected."""


class RollbackRequiredError(ElitzeError):
    """A production change is missing its mandatory rollback plan."""
