"""The engine ledger — the single source of truth for money movements."""

from __future__ import annotations

from decimal import Decimal

from ..domain.enums import LedgerEntryType, RevenueSource
from ..domain.errors import RevenueVerificationError
from ..domain.metrics import money
from ..domain.models import ExecutionAction, LedgerEntry
from ..log import get_logger

log = get_logger("ledger")


class Ledger:
    def __init__(self, repository) -> None:
        self._repo = repository

    # ------------------------------------------------------------------ #
    def record_spend(
        self,
        experiment_id: str | None,
        strategy_id: str | None,
        amount: Decimal,
        currency: str,
        description: str,
        actions: list[ExecutionAction] | None = None,
    ) -> LedgerEntry:
        entry = LedgerEntry(
            experiment_id=experiment_id,
            strategy_id=strategy_id,
            entry_type=LedgerEntryType.SPEND,
            amount=money(amount),
            currency=currency,
            description=description,
            verified=True,  # internal, authoritative
        )
        saved = self._repo.add_ledger_entry(entry)
        log.info(
            "spend recorded",
            fields={
                "experiment_id": experiment_id,
                "amount": str(saved.amount),
                "actions": [a.name for a in (actions or [])],
            },
        )
        return saved

    def record_reinvestment(
        self,
        experiment_id: str | None,
        strategy_id: str | None,
        amount: Decimal,
        currency: str,
        description: str = "reinvestment",
    ) -> LedgerEntry:
        entry = LedgerEntry(
            experiment_id=experiment_id,
            strategy_id=strategy_id,
            entry_type=LedgerEntryType.REINVESTMENT,
            amount=money(amount),
            currency=currency,
            description=description,
            verified=True,
        )
        return self._repo.add_ledger_entry(entry)

    def record_revenue(
        self,
        experiment_id: str | None,
        strategy_id: str | None,
        amount: Decimal,
        currency: str,
        source: RevenueSource,
        reference: str,
        description: str = "revenue",
    ) -> LedgerEntry:
        """Record *verified* revenue. Idempotent on ``reference``."""
        if amount < 0:
            raise RevenueVerificationError("negative revenue rejected")
        existing = self._repo.find_entry_by_reference(reference)
        if existing is not None:
            log.info("revenue reference already present (idempotent)", fields={"reference": reference})
            return existing
        entry = LedgerEntry(
            experiment_id=experiment_id,
            strategy_id=strategy_id,
            entry_type=LedgerEntryType.REVENUE,
            amount=money(amount),
            currency=currency,
            description=description,
            source=source,
            verified=True,
            reference=reference,
        )
        saved = self._repo.add_ledger_entry(entry)
        log.info(
            "revenue recorded (verified)",
            fields={"experiment_id": experiment_id, "amount": str(saved.amount), "source": source.value},
        )
        return saved

    # ------------------------------------------------------------------ #
    def verified_revenue(self, experiment_id: str | None = None) -> Decimal:
        return self._repo.verified_revenue(experiment_id)

    def spend(self, experiment_id: str | None = None) -> Decimal:
        return self._repo.spend(experiment_id)

    def balance(self) -> Decimal:
        return self._repo.pool_balance()
