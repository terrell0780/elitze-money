"""Repository layer: domain <-> persistence mapping.

All money handling uses Decimal and all timestamps are UTC. Revenue is only
ever *read* from verified ledger entries — never synthesized here.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from ..domain.enums import (
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
from ..domain.models import (
    Agent,
    BudgetAllocation,
    Evaluation,
    ExecutionResult,
    Experiment,
    ExperimentCandidate,
    ExperimentModel,
    ImprovementPlan,
    LedgerEntry,
    Measurement,
    PromotionDecision,
    Strategy,
    Task,
)
from .db import Database
from .orm import (
    AgentRow,
    AuditEventRow,
    CandidateRow,
    ExperimentRow,
    LedgerEntryRow,
    StrategyRow,
    TaskRow,
    WebhookEventRow,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _d(value: object) -> Decimal:
    return Decimal(str(value))


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Strategies
    # ------------------------------------------------------------------ #
    def save_strategy(self, strategy: Strategy) -> Strategy:
        with self.db.session() as s:
            row = s.get(StrategyRow, strategy.id)
            if row is None:
                row = StrategyRow(id=strategy.id)
                s.add(row)
            row.name = strategy.name
            row.engine = strategy.engine.value
            row.version = strategy.version
            row.parent_strategy = strategy.parent_strategy
            row.thesis = strategy.thesis
            row.target_market = strategy.target_market
            row.config = strategy.config
            s.commit()
            return strategy

    def get_strategy(self, strategy_id: str) -> Strategy | None:
        with self.db.session() as s:
            row = s.get(StrategyRow, strategy_id)
            if row is None:
                return None
            return Strategy(
                id=row.id,
                name=row.name,
                engine=EngineType(row.engine),
                version=row.version,
                parent_strategy=row.parent_strategy,
                thesis=row.thesis,
                target_market=row.target_market,
                config=row.config or {},
            )

    def list_strategies(self, engine: EngineType | None = None) -> list[Strategy]:
        stmt = select(StrategyRow).order_by(StrategyRow.updated_at.desc())
        if engine is not None:
            stmt = stmt.where(StrategyRow.engine == engine.value)
        with self.db.session() as s:
            rows = s.scalars(stmt).all()
            return [
                Strategy(
                    id=r.id,
                    name=r.name,
                    engine=EngineType(r.engine),
                    version=r.version,
                    parent_strategy=r.parent_strategy,
                    thesis=r.thesis,
                    target_market=r.target_market,
                    config=r.config or {},
                )
                for r in rows
            ]

    def next_version(self, base_name: str, engine: EngineType) -> int:
        strategies = [s for s in self.list_strategies(engine) if s.name == base_name]
        if not strategies:
            return 0
        return max(s.version for s in strategies) + 1

    # ------------------------------------------------------------------ #
    # Candidates
    # ------------------------------------------------------------------ #
    def save_candidates(self, candidates: Iterable[ExperimentCandidate]) -> list[ExperimentCandidate]:
        saved = list(candidates)
        with self.db.session() as s:
            for c in saved:
                row = s.get(CandidateRow, c.id)
                if row is None:
                    row = CandidateRow(id=c.id)
                    s.add(row)
                row.engine = c.engine.value
                row.title = c.title
                row.thesis = c.thesis
                row.target_market = c.target_market
                row.estimated_cost = c.estimated_cost
                row.expected_roi_min = c.expected_roi_min
                row.complexity = c.complexity
                row.tags = c.tags
                row.score = c.score
                row.status = c.status.value
                row.source = c.source
            s.commit()
        return saved

    def list_candidates(
        self,
        engine: EngineType | None = None,
        status: CandidateStatus | None = None,
        limit: int = 100,
    ) -> list[ExperimentCandidate]:
        stmt = select(CandidateRow).order_by(CandidateRow.score.desc()).limit(limit)
        if engine is not None:
            stmt = stmt.where(CandidateRow.engine == engine.value)
        if status is not None:
            stmt = stmt.where(CandidateRow.status == status.value)
        with self.db.session() as s:
            rows = s.scalars(stmt).all()
            return [
                ExperimentCandidate(
                    id=r.id,
                    engine=EngineType(r.engine),
                    title=r.title,
                    thesis=r.thesis,
                    target_market=r.target_market,
                    estimated_cost=r.estimated_cost,
                    expected_roi_min=r.expected_roi_min,
                    complexity=r.complexity,
                    tags=r.tags or [],
                    score=r.score,
                    status=CandidateStatus(r.status),
                    source=r.source,
                )
                for r in rows
            ]

    def set_candidate_status(self, candidate_id: str, status: CandidateStatus) -> None:
        with self.db.session() as s:
            row = s.get(CandidateRow, candidate_id)
            if row is not None:
                row.status = status.value
                s.commit()

    # ------------------------------------------------------------------ #
    # Experiments
    # ------------------------------------------------------------------ #
    def save_experiment(self, exp: Experiment) -> Experiment:
        with self.db.session() as s:
            row = s.get(ExperimentRow, exp.id)
            if row is None:
                row = ExperimentRow(id=exp.id)
                s.add(row)
            row.strategy_id = exp.strategy_id
            row.version = exp.version
            row.parent_strategy = exp.parent_strategy
            row.engine = exp.engine.value
            row.title = exp.title
            row.mode = exp.mode.value
            row.status = exp.status.value
            row.execution_cost = exp.execution_cost
            row.revenue = exp.revenue
            row.profit = exp.profit
            row.roi = exp.roi
            row.conversion_rate = exp.conversion_rate
            row.execution_time = exp.execution_time
            row.failures = exp.failures
            row.policy_result = exp.policy_result.value if exp.policy_result else None
            row.promotion_status = exp.promotion_status.value
            row.rollback_plan = exp.rollback_plan
            row.tags = exp.tags
            row.budget = exp.budget.model_dump(mode="json") if exp.budget else None
            row.model = exp.model.model_dump(mode="json") if exp.model else None
            row.execution = exp.execution.model_dump(mode="json") if exp.execution else None
            row.measurement = exp.measurement.model_dump(mode="json") if exp.measurement else None
            row.evaluation = exp.evaluation.model_dump(mode="json") if exp.evaluation else None
            row.improvement = exp.improvement.model_dump(mode="json") if exp.improvement else None
            row.decision = exp.decision.model_dump(mode="json") if exp.decision else None
            s.commit()
            return exp

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        with self.db.session() as s:
            row = s.get(ExperimentRow, experiment_id)
            if row is None:
                return None
            return self._row_to_experiment(row)

    def list_experiments(
        self,
        status: ExperimentStatus | None = None,
        engine: EngineType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Experiment]:
        stmt = select(ExperimentRow).order_by(ExperimentRow.created_at.desc()).limit(limit).offset(offset)
        if status is not None:
            stmt = stmt.where(ExperimentRow.status == status.value)
        if engine is not None:
            stmt = stmt.where(ExperimentRow.engine == engine.value)
        with self.db.session() as s:
            rows = s.scalars(stmt).all()
            return [self._row_to_experiment(r) for r in rows]

    @staticmethod
    def _row_to_experiment(row: ExperimentRow) -> Experiment:
        return Experiment(
            id=row.id,
            strategy_id=row.strategy_id,
            version=row.version,
            parent_strategy=row.parent_strategy,
            engine=EngineType(row.engine),
            title=row.title,
            mode=ExecutionMode(row.mode),
            status=ExperimentStatus(row.status),
            budget=BudgetAllocation.model_validate(row.budget) if row.budget else None,
            execution_cost=_d(row.execution_cost),
            revenue=_d(row.revenue),
            profit=_d(row.profit),
            roi=None if row.roi is None else _d(row.roi),
            conversion_rate=None if row.conversion_rate is None else _d(row.conversion_rate),
            execution_time=row.execution_time,
            failures=row.failures or [],
            policy_result=PolicyDecision(row.policy_result) if row.policy_result else None,
            promotion_status=PromotionStatus(row.promotion_status),
            rollback_plan=row.rollback_plan,
            model=ExperimentModel.model_validate(row.model) if row.model else None,
            execution=ExecutionResult.model_validate(row.execution) if row.execution else None,
            measurement=Measurement.model_validate(row.measurement) if row.measurement else None,
            evaluation=Evaluation.model_validate(row.evaluation) if row.evaluation else None,
            improvement=ImprovementPlan.model_validate(row.improvement) if row.improvement else None,
            decision=PromotionDecision.model_validate(row.decision) if row.decision else None,
            tags=row.tags or [],
        )

    # ------------------------------------------------------------------ #
    # Ledger
    # ------------------------------------------------------------------ #
    def add_ledger_entry(self, entry: LedgerEntry) -> LedgerEntry:
        with self.db.session() as s:
            row = LedgerEntryRow(
                id=entry.id,
                experiment_id=entry.experiment_id,
                strategy_id=entry.strategy_id,
                entry_type=entry.entry_type.value,
                amount=entry.amount,
                currency=entry.currency,
                description=entry.description,
                source=entry.source.value if entry.source else None,
                verified=entry.verified,
                reference=entry.reference,
            )
            s.add(row)
            s.commit()
            return entry

    def ledger_entries(self, experiment_id: str | None = None, limit: int = 200) -> list[LedgerEntry]:
        stmt = select(LedgerEntryRow).order_by(LedgerEntryRow.created_at.desc()).limit(limit)
        if experiment_id is not None:
            stmt = stmt.where(LedgerEntryRow.experiment_id == experiment_id)
        with self.db.session() as s:
            rows = s.scalars(stmt).all()
            return [
                LedgerEntry(
                    id=r.id,
                    experiment_id=r.experiment_id,
                    strategy_id=r.strategy_id,
                    entry_type=LedgerEntryType(r.entry_type),
                    amount=_d(r.amount),
                    currency=r.currency,
                    description=r.description,
                    source=RevenueSource(r.source) if r.source else None,
                    verified=r.verified,
                    reference=r.reference,
                    created_at=r.created_at,
                )
                for r in rows
            ]

    def verified_revenue(self, experiment_id: str | None = None) -> Decimal:
        stmt = select(LedgerEntryRow).where(
            LedgerEntryRow.entry_type == LedgerEntryType.REVENUE.value,
            LedgerEntryRow.verified.is_(True),
        )
        if experiment_id is not None:
            stmt = stmt.where(LedgerEntryRow.experiment_id == experiment_id)
        with self.db.session() as s:
            rows = s.scalars(stmt).all()
        return sum((_d(r.amount) for r in rows), Decimal("0.00"))

    def spend(self, experiment_id: str | None = None) -> Decimal:
        stmt = select(LedgerEntryRow).where(LedgerEntryRow.entry_type == LedgerEntryType.SPEND.value)
        if experiment_id is not None:
            stmt = stmt.where(LedgerEntryRow.experiment_id == experiment_id)
        with self.db.session() as s:
            rows = s.scalars(stmt).all()
        return sum((_d(r.amount) for r in rows), Decimal("0.00"))

    def pool_balance(self) -> Decimal:
        """Available reinvestment pool = verified revenue - spend."""
        return self.verified_revenue() - self.spend()

    def find_entry_by_reference(self, reference: str) -> LedgerEntry | None:
        with self.db.session() as s:
            row = s.scalars(
                select(LedgerEntryRow).where(LedgerEntryRow.reference == reference)
            ).first()
            if row is None:
                return None
            return LedgerEntry(
                id=row.id,
                experiment_id=row.experiment_id,
                strategy_id=row.strategy_id,
                entry_type=LedgerEntryType(row.entry_type),
                amount=_d(row.amount),
                currency=row.currency,
                description=row.description,
                source=RevenueSource(row.source) if row.source else None,
                verified=row.verified,
                reference=row.reference,
                created_at=row.created_at,
            )

    # ------------------------------------------------------------------ #
    # Audit trail
    # ------------------------------------------------------------------ #
    def audit(self, action: str, entity: str | None = None, detail: dict[str, Any] | None = None,
              actor: str = "system") -> None:
        with self.db.session() as s:
            s.add(AuditEventRow(action=action, entity=entity, detail=detail or {}, actor=actor))
            s.commit()

    # ------------------------------------------------------------------ #
    # Webhook events (revenue ingestion, idempotent)
    # ------------------------------------------------------------------ #
    def record_webhook(self, provider: str, event_id: str, verified: bool, payload: dict[str, Any]) -> bool:
        """Record a webhook event. Returns False if already seen (idempotent)."""
        with self.db.session() as s:
            existing = s.scalars(
                select(WebhookEventRow).where(WebhookEventRow.event_id == event_id)
            ).first()
            if existing is not None:
                return False
            s.add(
                WebhookEventRow(
                    provider=provider, event_id=event_id, verified=verified, payload=payload
                )
            )
            s.commit()
            return True

    # ------------------------------------------------------------------ #
    # Agents & tasks (OpenClaw runtime)
    # ------------------------------------------------------------------ #
    def upsert_agent(self, agent: Agent) -> Agent:
        with self.db.session() as s:
            row = s.scalars(select(AgentRow).where(AgentRow.name == agent.name)).first()
            if row is None:
                row = AgentRow(name=agent.name)
                s.add(row)
            row.id = agent.id or row.id
            row.engine = agent.engine.value if agent.engine else None
            row.status = agent.status.value
            row.meta = agent.metadata
            s.commit()
            agent.id = row.id
            return agent

    def list_agents(self) -> list[Agent]:
        with self.db.session() as s:
            rows = s.scalars(select(AgentRow).order_by(AgentRow.name)).all()
            return [
                Agent(
                    id=r.id,
                    name=r.name,
                    engine=EngineType(r.engine) if r.engine else None,
                    status=AgentStatus(r.status),
                    heartbeat_at=r.heartbeat_at,
                    metadata=r.meta or {},
                )
                for r in rows
            ]

    def heartbeat(self, agent_name: str, status: AgentStatus = AgentStatus.RUNNING) -> None:
        with self.db.session() as s:
            row = s.scalars(select(AgentRow).where(AgentRow.name == agent_name)).first()
            if row is not None:
                row.status = status.value
                from datetime import datetime

                row.heartbeat_at = datetime.now(UTC)
                s.commit()

    def create_task(self, task: Task) -> Task:
        with self.db.session() as s:
            row = TaskRow(
                id=task.id,
                agent_id=task.agent_id,
                kind=task.kind,
                payload=task.payload,
                status=task.status.value,
            )
            s.add(row)
            s.commit()
            return task

    def get_task(self, task_id: str) -> Task | None:
        with self.db.session() as s:
            row = s.get(TaskRow, task_id)
            if row is None:
                return None
            return self._row_to_task(row)

    def list_pending_tasks(self, limit: int = 20) -> list[Task]:
        with self.db.session() as s:
            rows = s.scalars(
                select(TaskRow).where(TaskRow.status == TaskStatus.PENDING.value).limit(limit)
            ).all()
            return [self._row_to_task(r) for r in rows]

    def update_task(
        self,
        task_id: str,
        status: TaskStatus,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        with self.db.session() as s:
            row = s.get(TaskRow, task_id)
            if row is None:
                return
            row.status = status.value
            if result is not None:
                row.result = result
            if error is not None:
                row.error = error
            from datetime import datetime

            now = datetime.now(UTC)
            if status in (TaskStatus.RUNNING,) and row.started_at is None:
                row.started_at = now
            if status in (TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                row.finished_at = now
            s.commit()

    @staticmethod
    def _row_to_task(row: TaskRow) -> Task:
        return Task(
            id=row.id,
            agent_id=row.agent_id,
            kind=row.kind,
            payload=row.payload or {},
            status=TaskStatus(row.status),
            result=row.result or {},
            error=row.error,
            created_at=row.created_at,
            started_at=row.started_at,
            finished_at=row.finished_at,
        )
