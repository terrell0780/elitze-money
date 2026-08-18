"""Revenue engines.

Each engine implements a *real* execution pattern for its channel. Engines
spend real money and record spend in the ledger; they never fabricate
revenue — revenue enters the ledger only through the verified ingestion
pipeline (see ``elitze.revenue``).
"""

from __future__ import annotations

from .base import EngineContext, RevenueEngine, registry
from .catalog import (
    AffiliateEngine,
    B2BEngine,
    DigitalProductsEngine,
    LeadGenEngine,
    MarketIntelEngine,
    SaaSProspectingEngine,
)

__all__ = [
    "EngineContext",
    "RevenueEngine",
    "registry",
    "LeadGenEngine",
    "B2BEngine",
    "DigitalProductsEngine",
    "AffiliateEngine",
    "MarketIntelEngine",
    "SaaSProspectingEngine",
]
