"""Verified revenue ingestion.

A revenue webhook is accepted only when:

1. its HMAC signature verifies against the configured shared secret, and
2. the event has not already been ingested (idempotency).

Without a configured ``ELITZE_WEBHOOK_SECRET`` the ingestion endpoint refuses
to accept revenue (fail-closed), so revenue can never be fabricated through
an unsigned request.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from ..domain.enums import RevenueSource
from ..domain.errors import RevenueVerificationError
from ..domain.models import LedgerEntry
from ..log import get_logger

log = get_logger("revenue.ingestion")


def verify_signature(secret: str, body: bytes, signature: str) -> bool:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={digest}", signature)


@dataclass
class IngestedRevenue:
    entry: LedgerEntry
    duplicate: bool = False


def ingest_webhook(
    *,
    ledger,
    repository,
    secret: str | None,
    provider: str,
    event_id: str,
    experiment_id: str,
    strategy_id: str | None,
    amount: Decimal,
    currency: str,
    body: bytes,
    signature: str | None,
    payload: dict[str, Any],
) -> IngestedRevenue:
    """Verify and ingest a revenue webhook, idempotently.

    Raises :class:`RevenueVerificationError` on any failed check.
    """
    if not secret:
        raise RevenueVerificationError("webhook secret not configured; revenue ingestion disabled")
    if not signature:
        raise RevenueVerificationError("missing signature header")
    if not verify_signature(secret, body, signature):
        raise RevenueVerificationError("invalid signature")

    seen = not repository.record_webhook(provider, event_id, verified=True, payload=payload)
    if seen:
        log.info("duplicate webhook ignored", fields={"event_id": event_id})
        existing = repository.find_entry_by_reference(f"webhook:{event_id}")
        if existing is not None:
            return IngestedRevenue(entry=existing, duplicate=True)

    entry = ledger.record_revenue(
        experiment_id=experiment_id,
        strategy_id=strategy_id,
        amount=amount,
        currency=currency,
        source=RevenueSource.WEBHOOK,
        reference=f"webhook:{event_id}",
        description=f"revenue from {provider}",
    )
    log.info(
        "revenue webhook ingested",
        fields={"provider": provider, "event_id": event_id, "amount": str(amount)},
    )
    return IngestedRevenue(entry=entry)
