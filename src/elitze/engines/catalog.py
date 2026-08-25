"""Concrete revenue engines.

Each ``execute`` records a real, bounded spend against the ledger via
``ctx.ledger.record_spend`` (real mode) — this is what makes a REAL run
"real": money actually leaves the pool. Revenue is *not* returned by these
methods; it arrives later through the verified ingestion pipeline.
"""

from __future__ import annotations

from ..domain.enums import EngineType, ExecutionMode
from ..domain.models import ExecutionAction, ExecutionResult
from .base import EngineContext, registry


def _make_result(ctx: EngineContext, actions: list[ExecutionAction], spend) -> ExecutionResult:
    mode = ExecutionMode.REAL if (ctx.budget and ctx.budget.approved) else ExecutionMode.PAPER
    return ExecutionResult(
        mode=mode,
        actions=actions,
        spend=spend,
        currency=ctx.budget.currency if ctx.budget else "USD",
    )


@registry.register
class LeadGenEngine:
    """Paid lead acquisition: run ads / directory placements to a landing page."""

    engine_type = EngineType.LEAD_GENERATION

    def plan(self, ctx: EngineContext, thesis: str) -> list[ExecutionAction]:
        budget = ctx.budget.amount if ctx.budget else 500
        return [
            ExecutionAction(name="allocate_ad_budget", detail={"channel": "search_ads", "amount": str(budget)}),
            ExecutionAction(name="deploy_landing_page", detail={"variant": "v1", "thesis": thesis}),
            ExecutionAction(name="enable_tracking", detail={"pixels": ["purchase", "lead_form"]}),
        ]

    def execute(self, ctx: EngineContext, actions: list[ExecutionAction]) -> ExecutionResult:
        spend = sum((a.cost for a in actions), 0) or (ctx.budget.amount if ctx.budget else 0)
        if ctx.budget and ctx.budget.approved and spend > 0:
            ctx.ledger.record_spend(
                ctx.experiment_id, ctx.strategy_id, spend, ctx.budget.currency, "lead gen ad spend", actions
            )
        result = _make_result(ctx, actions, spend)
        result.tracking_ids = ["leadgen-pixel"]
        return result


@registry.register
class B2BEngine:
    """B2B outreach: verified-domain prospecting + personalized outreach cadence."""

    engine_type = EngineType.B2B_SERVICES

    def plan(self, ctx: EngineContext, thesis: str) -> list[ExecutionAction]:
        return [
            ExecutionAction(name="build_prospect_list", detail={"source": "verified_business_registry"}),
            ExecutionAction(name="send_outreach_cadence", detail={"touches": 5}),
            ExecutionAction(name="schedule_discovery_calls", detail={}),
        ]

    def execute(self, ctx: EngineContext, actions: list[ExecutionAction]) -> ExecutionResult:
        spend = sum((a.cost for a in actions), 0) or (ctx.budget.amount if ctx.budget else 0)
        if ctx.budget and ctx.budget.approved and spend > 0:
            ctx.ledger.record_spend(
                ctx.experiment_id, ctx.strategy_id, spend, ctx.budget.currency, "b2b outreach tooling", actions
            )
        result = _make_result(ctx, actions, spend)
        result.tracking_ids = ["b2b-crm-pipeline"]
        return result


@registry.register
class DigitalProductsEngine:
    """Create and sell digital products via a storefront."""

    engine_type = EngineType.DIGITAL_PRODUCTS

    def plan(self, ctx: EngineContext, thesis: str) -> list[ExecutionAction]:
        return [
            ExecutionAction(name="publish_product", detail={"format": "ebook", "thesis": thesis}),
            ExecutionAction(name="configure_storefront", detail={}),
            ExecutionAction(name="launch_promo", detail={"channel": "email"}),
        ]

    def execute(self, ctx: EngineContext, actions: list[ExecutionAction]) -> ExecutionResult:
        spend = sum((a.cost for a in actions), 0) or (ctx.budget.amount if ctx.budget else 0)
        if ctx.budget and ctx.budget.approved and spend > 0:
            ctx.ledger.record_spend(
                ctx.experiment_id, ctx.strategy_id, spend, ctx.budget.currency, "storefront + delivery", actions
            )
        result = _make_result(ctx, actions, spend)
        result.tracking_ids = ["storefront-order-hook"]
        return result


@registry.register
class AffiliateEngine:
    """Build comparison/review content driving affiliate links (disclosed)."""

    engine_type = EngineType.AFFILIATE_MARKETING

    def plan(self, ctx: EngineContext, thesis: str) -> list[ExecutionAction]:
        return [
            ExecutionAction(name="publish_review_content", detail={"disclosure": "affiliate"}),
            ExecutionAction(name="join_affiliate_programs", detail={"niche": thesis}),
            ExecutionAction(name="track_clicks", detail={}),
        ]

    def execute(self, ctx: EngineContext, actions: list[ExecutionAction]) -> ExecutionResult:
        spend = sum((a.cost for a in actions), 0) or (ctx.budget.amount if ctx.budget else 0)
        if ctx.budget and ctx.budget.approved and spend > 0:
            ctx.ledger.record_spend(
                ctx.experiment_id, ctx.strategy_id, spend, ctx.budget.currency, "content production", actions
            )
        result = _make_result(ctx, actions, spend)
        result.tracking_ids = ["affiliate-click-id"]
        return result


@registry.register
class MarketIntelEngine:
    """Produce and sell market intelligence reports (data subscriptions)."""

    engine_type = EngineType.MARKET_INTELLIGENCE

    def plan(self, ctx: EngineContext, thesis: str) -> list[ExecutionAction]:
        return [
            ExecutionAction(name="collect_public_data", detail={"sources": ["public_filings", "web"]}),
            ExecutionAction(name="produce_report", detail={"segment": thesis}),
            ExecutionAction(name="open_subscriptions", detail={}),
        ]

    def execute(self, ctx: EngineContext, actions: list[ExecutionAction]) -> ExecutionResult:
        spend = sum((a.cost for a in actions), 0) or (ctx.budget.amount if ctx.budget else 0)
        if ctx.budget and ctx.budget.approved and spend > 0:
            ctx.ledger.record_spend(
                ctx.experiment_id, ctx.strategy_id, spend, ctx.budget.currency, "data + report production", actions
            )
        result = _make_result(ctx, actions, spend)
        result.tracking_ids = ["intel-subscription-hook"]
        return result


@registry.register
class SaaSProspectingEngine:
    """Validate and launch a small SaaS/MVP opportunity."""

    engine_type = EngineType.SAAS

    def plan(self, ctx: EngineContext, thesis: str) -> list[ExecutionAction]:
        return [
            ExecutionAction(name="build_mvp", detail={"scope": "minimal"}),
            ExecutionAction(name="landing_waitlist", detail={"thesis": thesis}),
            ExecutionAction(name="collect_waitlist", detail={}),
        ]

    def execute(self, ctx: EngineContext, actions: list[ExecutionAction]) -> ExecutionResult:
        spend = sum((a.cost for a in actions), 0) or (ctx.budget.amount if ctx.budget else 0)
        if ctx.budget and ctx.budget.approved and spend > 0:
            ctx.ledger.record_spend(
                ctx.experiment_id, ctx.strategy_id, spend, ctx.budget.currency, "MVP infra", actions
            )
        result = _make_result(ctx, actions, spend)
        result.tracking_ids = ["waitlist-form"]
        return result
