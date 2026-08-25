"""Tests for the verified ledger and revenue ingestion."""

from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal

import pytest

from elitze.domain.enums import RevenueSource
from elitze.domain.errors import RevenueVerificationError
from elitze.revenue import ingest_webhook, verify_signature


def test_signature_verification() -> None:
    body = b'{"amount":"10.00"}'
    sig = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert verify_signature("secret", body, sig) is True
    assert verify_signature("wrong", body, sig) is False


def test_ledger_spend_and_revenue(engine) -> None:
    engine.ledger.record_spend("exp1", "strat1", Decimal("100"), "USD", "test spend")
    assert engine.ledger.spend("exp1") == Decimal("100.00")
    engine.ledger.record_revenue(
        "exp1", "strat1", Decimal("250"), "USD", RevenueSource.WEBHOOK, "ref1", "sale"
    )
    assert engine.ledger.verified_revenue("exp1") == Decimal("250.00")
    assert engine.ledger.balance() == Decimal("150.00")


def test_revenue_idempotent_by_reference(engine) -> None:
    engine.ledger.record_revenue(
        "exp1", None, Decimal("50"), "USD", RevenueSource.WEBHOOK, "ref-dup"
    )
    engine.ledger.record_revenue(
        "exp1", None, Decimal("50"), "USD", RevenueSource.WEBHOOK, "ref-dup"
    )
    assert engine.ledger.verified_revenue("exp1") == Decimal("50.00")


def test_webhook_requires_signature(engine) -> None:
    with pytest.raises(RevenueVerificationError):
        ingest_webhook(
            ledger=engine.ledger,
            repository=engine.repo,
            secret="test-secret",
            provider="stripe",
            event_id="e1",
            experiment_id="exp1",
            strategy_id=None,
            amount=Decimal("10"),
            currency="USD",
            body=b"{}",
            signature=None,
            payload={},
        )


def test_webhook_ingest_and_reconcile(engine) -> None:
    body = b'{"event_id":"evt-9","experiment_id":"exp1","amount":"75.00","currency":"USD"}'
    sig = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    ingested = ingest_webhook(
        ledger=engine.ledger,
        repository=engine.repo,
        secret="test-secret",
        provider="stripe",
        event_id="evt-9",
        experiment_id="exp1",
        strategy_id=None,
        amount=Decimal("75.00"),
        currency="USD",
        body=body,
        signature=sig,
        payload={"event_id": "evt-9", "amount": "75.00"},
    )
    assert ingested.duplicate is False
    assert engine.ledger.verified_revenue("exp1") == Decimal("75.00")
    # Duplicate event is idempotent.
    again = ingest_webhook(
        ledger=engine.ledger,
        repository=engine.repo,
        secret="test-secret",
        provider="stripe",
        event_id="evt-9",
        experiment_id="exp1",
        strategy_id=None,
        amount=Decimal("75.00"),
        currency="USD",
        body=body,
        signature=sig,
        payload={"event_id": "evt-9", "amount": "75.00"},
    )
    assert again.duplicate is True
    assert engine.ledger.verified_revenue("exp1") == Decimal("75.00")
