"""Canonical domain models (pydantic) — the engine's data model.

These mirror the README data model and are the wire format between the
orchestrator nodes, the storage layer, and the API.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    AgentStatus,
    CandidateStatus,
    EngineType,
    ExecutionMode,
    ExperimentStatus,
    LedgerEntryType,
    PolicyDecision,
    PromotionStatus,
    RevenueSource,
    TaskStatus,
)

DEFAULT_CURRENCY = "USD"


def now_utc() -> datetime:
    return datetime.now(UTC)


class IDModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(default_factory=lambda: uuid4().hex)


# --------------------------------------------------------------------------- #
# Strategy (README: strategy ID, version, parent strategy)
# --------------------------------------------------------------------------- #
class Strategy(IDModel):
    name: str
    engine: EngineType
    version: int = Field(ge=0, default=0)
    parent_strategy: str | None = None
    thesis: str = ""
    target_market: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)


# --------------------------------------------------------------------------- #
# Experiment candidates (DISCOVER -> QUALIFY)
# --------------------------------------------------------------------------- #
class ExperimentCandidate(IDModel):
    engine: EngineType
    title: str
    thesis: str
    target_market: str
    estimated_cost: Decimal = Field(default=Decimal("0.00"))
    expected_roi_min: Decimal = Field(default=Decimal("0.00"))
    complexity: int = Field(ge=1, le=5, default=3)
    tags: list[str] = Field(default_factory=list)
    score: Decimal = Field(default=Decimal("0.00"))
    status: CandidateStatus = CandidateStatus.DISCOVERED
    source: str = "discover"


# --------------------------------------------------------------------------- #
# Experiment model (MODEL)
# --------------------------------------------------------------------------- #
class ExperimentModel(IDModel):
    strategy_id: str | None = None
    engine: EngineType
    title: str
    thesis: str
    assumptions: dict[str, Any] = Field(default_factory=dict)
    success_metrics: list[str] = Field(default_factory=list)
    stop_loss: Decimal = Field(default=Decimal("0.00"))
    mode: ExecutionMode = ExecutionMode.PAPER
    created_at: datetime = Field(default_factory=now_utc)


# --------------------------------------------------------------------------- #
# Budget (BUDGET)
# --------------------------------------------------------------------------- #
class BudgetAllocation(IDModel):
    amount: Decimal = Field(gt=0)
    currency: str = DEFAULT_CURRENCY
    source: str = "reinvestment_pool"
    approved: bool = False
    policy_decision: PolicyDecision = PolicyDecision.NEEDS_REVIEW
    notes: str = ""
    created_at: datetime = Field(default_factory=now_utc)


# --------------------------------------------------------------------------- #
# Execution (EXECUTE)
# --------------------------------------------------------------------------- #
class ExecutionAction(BaseModel):
    name: str
    detail: dict[str, Any] = Field(default_factory=dict)
    cost: Decimal = Field(default=Decimal("0.00"))
    at: datetime = Field(default_factory=now_utc)


class ExecutionResult(BaseModel):
    mode: ExecutionMode
    status: str = "succeeded"
    actions: list[ExecutionAction] = Field(default_factory=list)
    tracking_ids: list[str] = Field(default_factory=list)
    spend: Decimal = Field(default=Decimal("0.00"))
    currency: str = DEFAULT_CURRENCY
    errors: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=now_utc)
    finished_at: datetime = Field(default_factory=now_utc)


# --------------------------------------------------------------------------- #
# Measurement (MEASURE)
# --------------------------------------------------------------------------- #
class Measurement(BaseModel):
    """A measured result.

    ``revenue`` is only ever populated from the *verified* ledger. If
    ``simulated`` is True, the numbers are explicitly labeled as a paper run.
    """

    revenue: Decimal = Field(default=Decimal("0.00"))
    spend: Decimal = Field(default=Decimal("0.00"))
    conversions: int = Field(default=0, ge=0)
    impressions: int = Field(default=0, ge=0)
    currency: str = DEFAULT_CURRENCY
    simulated: bool = True
    source: str = "none"
    measured_at: datetime = Field(default_factory=now_utc)

    @property
    def profit(self) -> Decimal:
        return self.revenue - self.spend

    @property
    def roi(self) -> Decimal | None:
        if self.spend == 0:
            return None
        return (self.profit / self.spend) * 100

    @property
    def conversion_rate(self) -> Decimal | None:
        if self.impressions == 0:
            return None
        return (Decimal(self.conversions) / Decimal(self.impressions)) * 100


# --------------------------------------------------------------------------- #
# Evaluation (EVALUATE)
# --------------------------------------------------------------------------- #
class Evaluation(BaseModel):
    verdict: str
    roi: Decimal | None = None
    conversion_rate: Decimal | None = None
    profit: Decimal = Decimal("0.00")
    failures: list[str] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)
    should_improve: bool = False
    profile: dict[str, Any] = Field(default_factory=dict)
    evaluated_at: datetime = Field(default_factory=now_utc)


# --------------------------------------------------------------------------- #
# Improvement (IMPROVE / TEST) — recursive optimization
# --------------------------------------------------------------------------- #
class Improvement(BaseModel):
    """A generated candidate version of some artifact."""

    artifact: str  # e.g. "strategy", "offer", "landing_page", "prompt", "workflow"
    description: str
    changes: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class ImprovementPlan(BaseModel):
    candidate_versions: list[Improvement] = Field(default_factory=list)
    champion: dict[str, Any] | None = None
    champion_score: Decimal = Decimal("0.00")
    challenger: list[dict[str, Any]] | None = None
    challenger_score: Decimal = Decimal("0.00")
    winner: str | None = None  # "champion" | "challenger"


# --------------------------------------------------------------------------- #
# Promotion / kill decision (PROMOTE / KILL)
# --------------------------------------------------------------------------- #
class PromotionDecision(BaseModel):
    promotion_status: PromotionStatus
    policy_decision: PolicyDecision
    reason: str = ""
    rollback_plan: str = ""
    decided_at: datetime = Field(default_factory=now_utc)


# --------------------------------------------------------------------------- #
# Ledger
# --------------------------------------------------------------------------- #
class LedgerEntry(IDModel):
    experiment_id: str | None = None
    strategy_id: str | None = None
    entry_type: LedgerEntryType
    amount: Decimal
    currency: str = DEFAULT_CURRENCY
    description: str = ""
    source: RevenueSource | None = None  # required for revenue entries
    verified: bool = False
    reference: str | None = None  # idempotency / external reference
    created_at: datetime = Field(default_factory=now_utc)


# --------------------------------------------------------------------------- #
# The full experiment record (README data model)
# --------------------------------------------------------------------------- #
class Experiment(IDModel):
    strategy_id: str | None = None
    version: int = Field(default=0, ge=0)
    parent_strategy: str | None = None
    engine: EngineType
    title: str
    mode: ExecutionMode = ExecutionMode.PAPER
    status: ExperimentStatus = ExperimentStatus.DRAFT
    budget: BudgetAllocation | None = None
    execution_cost: Decimal = Field(default=Decimal("0.00"))
    revenue: Decimal = Field(default=Decimal("0.00"))
    profit: Decimal = Field(default=Decimal("0.00"))
    roi: Decimal | None = None
    conversion_rate: Decimal | None = None
    execution_time: float | None = None  # seconds
    failures: list[str] = Field(default_factory=list)
    policy_result: PolicyDecision | None = None
    promotion_status: PromotionStatus = PromotionStatus.NONE
    rollback_plan: str = ""
    model: ExperimentModel | None = None
    execution: ExecutionResult | None = None
    measurement: Measurement | None = None
    evaluation: Evaluation | None = None
    improvement: ImprovementPlan | None = None
    decision: PromotionDecision | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


# --------------------------------------------------------------------------- #
# Agents & tasks (OpenClaw runtime)
# --------------------------------------------------------------------------- #
class Agent(IDModel):
    name: str
    engine: EngineType | None = None
    status: AgentStatus = AgentStatus.IDLE
    heartbeat_at: datetime = Field(default_factory=now_utc)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Task(IDModel):
    agent_id: str | None = None
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime = Field(default_factory=now_utc)
    started_at: datetime | None = None
    finished_at: datetime | None = None
