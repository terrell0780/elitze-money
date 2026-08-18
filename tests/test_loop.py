"""End-to-end tests for the orchestration loop."""

from __future__ import annotations

from decimal import Decimal

from elitze.domain.enums import EngineType, ExecutionMode, PromotionStatus, RevenueSource


def test_paper_run_completes_and_is_killed(engine) -> None:
    exp = engine.run_experiment(
        EngineType.LEAD_GENERATION,
        "paper run",
        mode=ExecutionMode.PAPER,
    )
    assert exp.id
    assert exp.mode == ExecutionMode.PAPER
    # Paper runs can never be promoted (no fabricated revenue).
    assert exp.promotion_status == PromotionStatus.KILLED
    assert exp.revenue == Decimal("0.00")
    # Persisted and retrievable.
    assert engine.get_experiment(exp.id) is not None


def test_real_run_spends_and_kills_without_revenue(engine) -> None:
    engine.seed_pool(Decimal("1000"))
    exp = engine.run_experiment(
        EngineType.SAAS,
        "real run",
        mode=ExecutionMode.REAL,
        rollback_plan="revert deployment and pause spend",
    )
    assert exp.execution_cost > 0  # real spend left the pool
    # A real run executes exactly once — no double-spend from the improve loop.
    assert exp.execution_cost == exp.budget.amount
    assert exp.revenue == Decimal("0.00")
    assert exp.profit < 0
    assert exp.promotion_status == PromotionStatus.KILLED
    assert engine.pool_balance() == Decimal("1000.00") - exp.execution_cost


def test_real_run_reconciles_with_verified_revenue(engine) -> None:
    engine.seed_pool(Decimal("1000"))
    exp = engine.run_experiment(
        EngineType.B2B_SERVICES,
        "promotable run",
        mode=ExecutionMode.REAL,
        rollback_plan="revert campaign",
    )
    # Verified revenue arrives afterwards and reconciles.
    engine.ledger.record_revenue(
        exp.id, exp.strategy_id, Decimal("500"), "USD",
        RevenueSource.WEBHOOK, "ref-promo", "consulting sale",
    )
    reconciled = engine.reconcile_experiment(exp.id)
    assert reconciled is not None
    assert reconciled.revenue == Decimal("500.00")
    assert reconciled.profit > 0


def test_list_experiments_filters(engine) -> None:
    engine.run_experiment(EngineType.LEAD_GENERATION, "listed", mode=ExecutionMode.PAPER)
    results = engine.list_experiments(limit=10)
    assert any(e.title == "listed" for e in results)
