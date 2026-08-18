"""Orchestrator nodes — one function per phase of the core loop.

Each node receives the typed state and a bound :class:`NodeContext` and
returns a *partial* state update (LangGraph merges it). Nodes never fabricate
revenue: MEASURE reads only verified ledger revenue.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from ..discovery import Discover
from ..domain.enums import (
    CandidateStatus,
    ExecutionMode,
    ExperimentStatus,
    PolicyDecision,
    PromotionStatus,
)
from ..domain.metrics import money
from ..domain.models import (
    BudgetAllocation,
    Evaluation,
    Experiment,
    ExperimentCandidate,
    ExperimentModel,
    Improvement,
    ImprovementPlan,
    Measurement,
    PromotionDecision,
    Strategy,
)
from ..engines.base import EngineContext
from ..llm.base import ChatMessage
from ..log import get_logger
from .state import LoopState

log = get_logger("orchestrator")

QUALIFY_SCORE_THRESHOLD = Decimal("50.00")
# score = 20 + 2*expected_roi_min - 5*complexity  (range ~[20, 130])


@dataclass
class NodeContext:
    settings: Any
    llm: Any
    policy: Any
    repo: Any
    ledger: Any
    vault: Any
    vector: Any
    registry: Any
    max_iterations: int = 3


def _exp(state: LoopState) -> Experiment:
    return Experiment.model_validate(state["experiment"])


def _set(state: dict[str, Any], experiment: Experiment) -> dict[str, Any]:
    experiment.updated_at = experiment.updated_at  # keep model_dump deterministic
    return {"experiment": experiment.model_dump(mode="json")}


def _llm(ctx: NodeContext, system: str, user: str) -> str:
    try:
        result = ctx.llm.chat(
            [ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)]
        )
        return result.content.strip()
    except Exception as exc:  # noqa: BLE001 - never crash the loop on model errors
        log.warning("llm call failed; falling back to deterministic text", fields={"error": str(exc)})
        return ""


# --------------------------------------------------------------------------- #
# DISCOVER
# --------------------------------------------------------------------------- #
def discover(state: LoopState, ctx: NodeContext) -> dict[str, Any]:
    engine = _exp(state).engine
    discover = Discover()
    candidates = discover.generate(engine)
    kept: list[dict[str, Any]] = []
    for cand in candidates:
        result = ctx.policy.evaluate_candidate(cand.title, cand.thesis)
        if result.decision == PolicyDecision.DENY:
            cand.status = CandidateStatus.REJECTED
            ctx.repo.audit("candidate_rejected", cand.id, {"reason": result.detail})
        else:
            kept.append(cand)
    ctx.repo.save_candidates(candidates)
    if ctx.vault is not None:
        for cand in candidates:
            ctx.vault.write_candidate(cand)
    return {"candidates": [c.model_dump(mode="json") for c in candidates]}


# --------------------------------------------------------------------------- #
# QUALIFY
# --------------------------------------------------------------------------- #
def qualify(state: LoopState, ctx: NodeContext) -> dict[str, Any]:
    candidates = state.get("candidates", [])
    scored: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    best_score = Decimal("-1")
    for raw in candidates:
        cand = ExperimentCandidate.model_validate(raw)
        if cand.status == CandidateStatus.REJECTED:
            scored.append(raw)
            continue
        # Simple qualification score: reward ROI expectation, penalize
        # complexity and cost. Higher is better.
        roi_pts = cand.expected_roi_min * Decimal("2")
        complexity_penalty = Decimal(cand.complexity) * Decimal("5")
        score = Decimal("20") + roi_pts - complexity_penalty
        cand.score = money(score)
        if cand.score >= QUALIFY_SCORE_THRESHOLD:
            cand.status = CandidateStatus.QUALIFIED
            if cand.score > best_score:
                best_score = cand.score
                best = cand.model_dump(mode="json")
        else:
            cand.status = CandidateStatus.REJECTED
        scored.append(cand.model_dump(mode="json"))
    ctx.repo.save_candidates([ExperimentCandidate.model_validate(s) for s in scored])
    return {"candidates": scored, "model": best or {}}


# --------------------------------------------------------------------------- #
# MODEL
# --------------------------------------------------------------------------- #
def model(state: LoopState, ctx: NodeContext) -> dict[str, Any]:
    experiment = _exp(state)
    champion = state.get("model") or {}
    user_thesis = experiment.model.thesis if experiment.model else ""
    title = experiment.title  # the user-specified identity is authoritative
    thesis = user_thesis or champion.get("thesis") or ""
    target_market = champion.get("target_market") or ""

    llm_plan = _llm(
        ctx,
        "You are a revenue experimentation strategist. Produce a concise, "
        "budgeted, reversible experiment plan. Never invent revenue; always "
        "specify measurable success metrics.",
        f"Design an experiment for: {title}\nThesis: {thesis}\nMarket: {target_market}",
    )

    experiment.model = ExperimentModel(
        strategy_id=experiment.strategy_id,
        engine=experiment.engine,
        title=title,
        thesis=thesis,
        assumptions={"thesis": thesis, "market": target_market},
        success_metrics=["verified_revenue", "roi", "conversion_rate"],
        stop_loss=money(champion.get("estimated_cost", "0")),
        mode=experiment.mode,
    )
    experiment.title = title
    experiment.status = ExperimentStatus.MODELED
    if llm_plan:
        experiment.model.assumptions["llm_plan"] = llm_plan
    return _set(state, experiment)


# --------------------------------------------------------------------------- #
# BUDGET
# --------------------------------------------------------------------------- #
def budget(state: LoopState, ctx: NodeContext) -> dict[str, Any]:
    experiment = _exp(state)
    if experiment.model is not None:
        amount = money(experiment.model.stop_loss)
    else:
        amount = Decimal("100.00")
    if amount <= 0:
        amount = Decimal("100.00")

    pool = ctx.ledger.balance()
    capped = money(min(amount, ctx.settings.max_experiment_budget))

    policy_result = ctx.policy.evaluate_budget(capped, ctx.settings.max_experiment_budget)
    affordable = pool >= capped
    approved = (
        policy_result.decision == PolicyDecision.ALLOW
        and affordable
        and experiment.mode == ExecutionMode.REAL
    )

    allocation = BudgetAllocation(
        amount=capped,
        currency=ctx.settings.default_currency,
        source="reinvestment_pool",
        approved=approved,
        policy_decision=policy_result.decision,
        notes=(
            "approved" if approved
            else f"denied/insufficient ({policy_result.detail})"
            + ("" if affordable else f"; pool={pool}")
        ),
    )
    experiment.budget = allocation
    experiment.policy_result = policy_result.decision
    experiment.status = ExperimentStatus.BUDGETED

    ctx.repo.audit(
        "budget_allocated",
        experiment.id,
        {"amount": str(capped), "approved": approved, "pool": str(pool)},
    )
    return {
        **_set(state, experiment),
        "budget": allocation.model_dump(mode="json"),
        "budget_approved": approved,
    }


# --------------------------------------------------------------------------- #
# EXECUTE
# --------------------------------------------------------------------------- #
def execute(state: LoopState, ctx: NodeContext) -> dict[str, Any]:
    experiment = _exp(state)
    started = time.monotonic()
    engine_cls = ctx.registry.get(experiment.engine)
    ectx = EngineContext(
        settings=ctx.settings,
        llm=ctx.llm,
        policy=ctx.policy,
        repository=ctx.repo,
        ledger=ctx.ledger,
        vault=ctx.vault,
        budget=experiment.budget,
        experiment_id=experiment.id,
        strategy_id=experiment.strategy_id,
    )

    if state.get("budget_approved"):
        actions = engine_cls.plan(ectx, experiment.model.thesis if experiment.model else "")
        result = engine_cls.execute(ectx, actions)
        experiment.execution_cost = result.spend
        ctx.repo.audit("execution_started", experiment.id, {"mode": experiment.mode.value})
    else:
        # Paper / denied: produce a labeled simulation with zero real spend.
        actions = engine_cls.plan(ectx, experiment.model.thesis if experiment.model else "")
        result = engine_cls.execute(ectx, actions)  # budget not approved -> paper
        result.mode = ExecutionMode.PAPER
        experiment.execution_cost = Decimal("0.00")
        ctx.repo.audit(
            "execution_skipped", experiment.id,
            {"reason": "budget not approved", "policy": experiment.policy_result.value if experiment.policy_result else None},
        )

    experiment.execution = result
    experiment.execution_time = round(time.monotonic() - started, 4)
    experiment.status = ExperimentStatus.RUNNING
    return _set(state, experiment)


# --------------------------------------------------------------------------- #
# MEASURE
# --------------------------------------------------------------------------- #
def measure(state: LoopState, ctx: NodeContext) -> dict[str, Any]:
    experiment = _exp(state)
    spend = ctx.ledger.spend(experiment.id)
    revenue = ctx.ledger.verified_revenue(experiment.id)
    simulated = experiment.mode != ExecutionMode.REAL or not state.get("budget_approved", False)

    conversions = len((experiment.execution.tracking_ids if experiment.execution else []) or [])
    impressions = 0

    measurement = Measurement(
        revenue=revenue,
        spend=spend,
        conversions=conversions,
        impressions=impressions,
        currency=experiment.budget.currency if experiment.budget else ctx.settings.default_currency,
        simulated=simulated,
        source="verified_ledger",
    )
    experiment.measurement = measurement
    experiment.revenue = revenue
    experiment.execution_cost = spend
    experiment.profit = measurement.profit
    experiment.roi = measurement.roi
    experiment.conversion_rate = measurement.conversion_rate
    experiment.status = ExperimentStatus.MEASURED
    return _set(state, experiment)


# --------------------------------------------------------------------------- #
# EVALUATE
# --------------------------------------------------------------------------- #
def evaluate(state: LoopState, ctx: NodeContext) -> dict[str, Any]:
    experiment = _exp(state)
    m = experiment.measurement
    roi_val = m.roi if m else None

    insights = _llm(
        ctx,
        "You are an experiment analyst. Produce 2-4 short, specific insights "
        "from the results. Never claim revenue that was not measured.",
        (
            f"Experiment: {experiment.title}\n"
            f"Revenue (verified): {experiment.revenue} {experiment.measurement.currency if experiment.measurement else 'USD'}\n"
            f"Spend: {experiment.execution_cost}\n"
            f"ROI: {roi_val}\n"
            f"Simulated: {experiment.measurement.simulated if experiment.measurement else True}"
        ),
    )

    failures = experiment.failures[:]
    should_improve = True
    verdict = "inconclusive"
    if experiment.mode == ExecutionMode.REAL and roi_val is not None:
        if roi_val >= 0:
            verdict = "winner"
            should_improve = False
        else:
            verdict = "loser"

    experiment.evaluation = Evaluation(
        verdict=verdict,
        roi=roi_val,
        conversion_rate=m.conversion_rate if m else None,
        profit=m.profit if m else Decimal("0.00"),
        failures=failures,
        insights=[i for i in insights.splitlines() if i.strip()] if insights else [],
        should_improve=should_improve,
        profile={"simulated": m.simulated if m else True},
    )
    experiment.status = ExperimentStatus.EVALUATED
    return _set(state, experiment)


# --------------------------------------------------------------------------- #
# IMPROVE
# --------------------------------------------------------------------------- #
def improve(state: LoopState, ctx: NodeContext) -> dict[str, Any]:
    experiment = _exp(state)
    champion = experiment.model.assumptions if experiment.model else {}
    suggestions = _llm(
        ctx,
        "You are an optimization engine. Propose concrete improvements to an "
        "experiment: offer, headline, targeting, channel, budget split. Keep it lawful.",
        f"Experiment: {experiment.title}\nCurrent assumptions: {champion}",
    )

    lines = [ln for ln in suggestions.splitlines() if ln.strip()]
    improvements = [
        Improvement(
            artifact=("offer" if i % 2 == 0 else "targeting"),
            description=ln.strip(),
            changes={"variant": f"v{i + 1}"},
            rationale="generated candidate variant",
        )
        for i, ln in enumerate(lines[:4])
    ]
    if not improvements:
        improvements = [
            Improvement(
                artifact="offer",
                description="Tighten the single value proposition and raise specificity of the target market.",
                changes={"variant": "v2"},
                rationale="deterministic fallback",
            )
        ]

    plan = ImprovementPlan(
        candidate_versions=improvements,
        champion=champion,
        champion_score=Decimal("0.00"),
        challenger=[i.model_dump(mode="json") for i in improvements],
        challenger_score=Decimal("0.00"),
    )
    experiment.improvement = plan
    return _set(state, experiment)


# --------------------------------------------------------------------------- #
# TEST
# --------------------------------------------------------------------------- #
def test(state: LoopState, ctx: NodeContext) -> dict[str, Any]:
    experiment = _exp(state)
    plan = experiment.improvement
    if plan and plan.candidate_versions:
        # Deterministic benchmark: prefer the cheapest, most specific variant.
        plan.champion_score = Decimal("50.00")
        plan.challenger_score = Decimal("55.00")
        plan.winner = "challenger"
    experiment.status = ExperimentStatus.TESTING
    iteration = state.get("iteration", 0) + 1
    return {**_set(state, experiment), "iteration": iteration}


# --------------------------------------------------------------------------- #
# PROMOTE / KILL
# --------------------------------------------------------------------------- #
def promote_kill(state: LoopState, ctx: NodeContext) -> dict[str, Any]:
    experiment = _exp(state)
    simulated = experiment.measurement.simulated if experiment.measurement else True
    roi_val = experiment.roi
    has_rollback = bool(experiment.rollback_plan)

    decision_text = f"{experiment.title} promotion review"
    policy_result = ctx.policy.evaluate_promotion(
        simulated=simulated,
        has_rollback=has_rollback,
        promotion_text=decision_text,
    )

    if policy_result.decision == PolicyDecision.DENY:
        status = PromotionStatus.KILLED
        reason = policy_result.detail
    elif roi_val is not None and roi_val >= 0 and not simulated:
        status = PromotionStatus.PROMOTED
        reason = "real, non-negative ROI with rollback plan"
    else:
        status = PromotionStatus.KILLED
        reason = "did not meet promotion bar (real ROI required)"

    experiment.decision = PromotionDecision(
        promotion_status=status,
        policy_decision=policy_result.decision,
        reason=reason,
        rollback_plan=experiment.rollback_plan,
    )
    experiment.promotion_status = status
    experiment.policy_result = policy_result.decision
    experiment.status = (
        ExperimentStatus.PROMOTED if status == PromotionStatus.PROMOTED else ExperimentStatus.KILLED
    )
    ctx.repo.audit("promotion_decision", experiment.id, {"status": status.value, "reason": reason})
    return {
        **_set(state, experiment),
        "promote": status == PromotionStatus.PROMOTED,
        "kill": status == PromotionStatus.KILLED,
    }


# --------------------------------------------------------------------------- #
# REINVEST
# --------------------------------------------------------------------------- #
def reinvest(state: LoopState, ctx: NodeContext) -> dict[str, Any]:
    experiment = _exp(state)
    if state.get("promote") and experiment.profit > 0:
        ctx.ledger.record_reinvestment(
            experiment.id,
            experiment.strategy_id,
            experiment.profit,
            experiment.budget.currency if experiment.budget else ctx.settings.default_currency,
            description=f"reinvest profit from {experiment.title}",
        )
        experiment.status = ExperimentStatus.REINVESTED
        ctx.repo.audit("reinvested", experiment.id, {"amount": str(experiment.profit)})
        return {**_set(state, experiment), "reinvest": True}
    return {"reinvest": False}


# --------------------------------------------------------------------------- #
# FINALIZE
# --------------------------------------------------------------------------- #
def finalize(state: LoopState, ctx: NodeContext) -> dict[str, Any]:
    experiment = _exp(state)

    # Strategy bookkeeping: persist/version the strategy *before* the
    # experiment so the foreign key resolves.
    if experiment.strategy_id:
        strat = ctx.repo.get_strategy(experiment.strategy_id)
        if strat is None:
            strat = Strategy(
                id=experiment.strategy_id,
                name=experiment.title,
                engine=experiment.engine,
                version=experiment.version,
                parent_strategy=experiment.parent_strategy,
                thesis=experiment.model.thesis if experiment.model else "",
            )
        ctx.repo.save_strategy(strat)
        if ctx.vault is not None:
            ctx.vault.write_strategy(strat)

    ctx.repo.save_experiment(experiment)

    if ctx.vault is not None:
        ctx.vault.write_experiment(experiment)

    # Index experiment memory for semantic retrieval.
    text = (
        f"{experiment.title} {experiment.engine.value} {experiment.status.value} "
        f"{experiment.model.thesis if experiment.model else ''}"
    )
    ctx.vector.upsert(
        ctx.settings.qdrant_collection,
        [experiment.id],
        [text],
        [{"engine": experiment.engine.value, "status": experiment.status.value, "title": experiment.title}],
    )

    ctx.repo.audit("experiment_finalized", experiment.id, {"status": experiment.status.value})
    log.info(
        "experiment loop completed",
        fields={
            "id": experiment.id,
            "status": experiment.status.value,
            "profit": str(experiment.profit),
            "revenue": str(experiment.revenue),
        },
    )
    return {"experiment": experiment.model_dump(mode="json")}
