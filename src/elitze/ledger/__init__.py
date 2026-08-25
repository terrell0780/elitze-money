"""Ledger: authoritative, auditable money movements.

Revenue entries require a verified source; spend entries are internal and
authoritative. All amounts are Decimal.
"""

from __future__ import annotations

from .ledger import Ledger

__all__ = ["Ledger"]
