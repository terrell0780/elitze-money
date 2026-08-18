"""Verified revenue ingestion.

Revenue enters the system *only* through verified external events. No code
path synthesizes revenue.
"""

from __future__ import annotations

from .ingestion import ingest_webhook, verify_signature

__all__ = ["verify_signature", "ingest_webhook"]
