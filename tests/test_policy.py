"""Tests for the safety-boundary policy engine."""

from __future__ import annotations

from decimal import Decimal

from elitze.domain.enums import PolicyDecision
from elitze.policy import PolicyEngine


def test_denies_disallowed_activity() -> None:
    engine = PolicyEngine()
    result = engine.evaluate_text("plan to send spam to everyone")
    assert result.decision == PolicyDecision.DENY
    assert "spam" in result.denied_terms


def test_allows_lawful_activity() -> None:
    engine = PolicyEngine()
    result = engine.evaluate_text("run a disclosed affiliate comparison site")
    assert result.decision == PolicyDecision.ALLOW


def test_budget_cap() -> None:
    engine = PolicyEngine()
    assert engine.evaluate_budget(Decimal("500"), Decimal("1000")).decision == PolicyDecision.ALLOW
    assert engine.evaluate_budget(Decimal("2000"), Decimal("1000")).decision == PolicyDecision.DENY


def test_promotion_requires_real_and_rollback() -> None:
    engine = PolicyEngine()
    # Simulated results can never be promoted.
    assert (
        engine.evaluate_promotion(simulated=True, has_rollback=True).decision
        == PolicyDecision.DENY
    )
    # Real results still require a rollback plan.
    assert (
        engine.evaluate_promotion(simulated=False, has_rollback=False).decision
        == PolicyDecision.DENY
    )
    # Real + rollback + clean text -> allow.
    assert (
        engine.evaluate_promotion(simulated=False, has_rollback=True).decision
        == PolicyDecision.ALLOW
    )
