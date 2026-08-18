"""SQLAlchemy ORM models.

First-class columns mirror the README data model (strategy ID, version,
parent strategy, execution cost, revenue, profit, ROI, conversion rate,
execution time, failures, policy result, promotion status) so the canonical
experiment truth is queryable without parsing JSON.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid4().hex


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"not JSON serializable: {type(obj)}")


def dumps_json(value: Any) -> str:
    return json.dumps(value, default=_json_default)


def loads_json(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)


class StrategyRow(TimestampMixin, Base):
    __tablename__ = "strategies"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255))
    engine: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer, default=0)
    parent_strategy: Mapped[str | None] = mapped_column(String(32), nullable=True)
    thesis: Mapped[str] = mapped_column(Text, default="")
    target_market: Mapped[str] = mapped_column(Text, default="")
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ExperimentRow(TimestampMixin, Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    strategy_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("strategies.id"), nullable=True, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=0)
    parent_strategy: Mapped[str | None] = mapped_column(String(32), nullable=True)
    engine: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(16), default="paper")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)

    execution_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    revenue: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    profit: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    roi: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    conversion_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    execution_time: Mapped[float | None] = mapped_column(nullable=True)

    failures: Mapped[list[str]] = mapped_column(JSON, default=list)
    policy_result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    promotion_status: Mapped[str] = mapped_column(String(32), default="none")
    rollback_plan: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Rich state blobs (model/budget/execution/measurement/evaluation/...)
    budget: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    model: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    execution: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    measurement: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    evaluation: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    improvement: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    decision: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    strategy: Mapped[StrategyRow | None] = relationship()


class LedgerEntryRow(TimestampMixin, Base):
    __tablename__ = "ledger"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    experiment_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    strategy_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    entry_type: Mapped[str] = mapped_column(String(32), index=True)  # spend|revenue|reinvestment
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CandidateRow(TimestampMixin, Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    engine: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    thesis: Mapped[str] = mapped_column(Text, default="")
    target_market: Mapped[str] = mapped_column(Text, default="")
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    expected_roi_min: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    complexity: Mapped[int] = mapped_column(Integer, default=3)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    score: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(32), default="discovered", index=True)
    source: Mapped[str] = mapped_column(String(64), default="discover")


class AuditEventRow(TimestampMixin, Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String(128), default="system")
    action: Mapped[str] = mapped_column(String(128), index=True)
    entity: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AgentRow(TimestampMixin, Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    engine: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="idle")
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)


class TaskRow(TimestampMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    agent_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(128), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WebhookEventRow(TimestampMixin, Base):
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    event_id: Mapped[str] = mapped_column(String(255), index=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
