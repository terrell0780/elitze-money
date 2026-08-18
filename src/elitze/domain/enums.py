"""Enumerations shared across the engine."""

from __future__ import annotations

from enum import StrEnum


class EngineType(StrEnum):
    """The six supported revenue engines (README: Revenue Engines)."""

    LEAD_GENERATION = "lead_generation"
    B2B_SERVICES = "b2b_services"
    DIGITAL_PRODUCTS = "digital_products"
    AFFILIATE_MARKETING = "affiliate_marketing"
    MARKET_INTELLIGENCE = "market_intelligence"
    SAAS = "saas"


class ExecutionMode(StrEnum):
    """How an experiment is executed.

    ``REAL``  -> real spend, real actions, and revenue only from *verified*
                 external events (webhooks/integrations).
    ``PAPER`` -> a labeled simulation used for testing the loop. Results are
                 flagged ``simulated=True`` and can never be promoted, counted
                 as real revenue, or used to justify production spend.
    """

    REAL = "real"
    PAPER = "paper"


class ExperimentStatus(StrEnum):
    DRAFT = "draft"
    QUALIFIED = "qualified"
    MODELED = "modeled"
    BUDGETED = "budgeted"
    RUNNING = "running"
    MEASURED = "measured"
    EVALUATED = "evaluated"
    TESTING = "testing"
    PROMOTED = "promoted"
    KILLED = "killed"
    REINVESTED = "reinvested"
    REJECTED = "rejected"
    FAILED = "failed"


class PromotionStatus(StrEnum):
    NONE = "none"
    CANDIDATE = "candidate"
    PROMOTED = "promoted"
    KILLED = "killed"
    ROLLED_BACK = "rolled_back"


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    NEEDS_REVIEW = "needs_review"


class LedgerEntryType(StrEnum):
    SPEND = "spend"
    REVENUE = "revenue"
    REINVESTMENT = "reinvestment"


class RevenueSource(StrEnum):
    """A *verified* origin for revenue.

    Note the absence of anything like ``simulated`` — simulated earnings are
    never admitted to the ledger as revenue.
    """

    WEBHOOK = "webhook"
    INTEGRATION = "integration"
    MANUAL_VERIFIED = "manual_verified"


class CandidateStatus(StrEnum):
    DISCOVERED = "discovered"
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    MODELED = "modeled"


class AgentStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    FAILED = "failed"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
