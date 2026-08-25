"""Shared test fixtures.

Tests run against an isolated SQLite database and an in-memory vector store,
so they never touch the developer's real data or Qdrant directory.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure the source tree is importable regardless of how pytest is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Isolate test data away from any real runtime state.
_TMP = tempfile.mkdtemp(prefix="elitze-test-")
os.environ.setdefault("ELITZE_DATA_DIR", _TMP)
os.environ.setdefault("ELITZE_VAULT_DIR", os.path.join(_TMP, "vault"))
os.environ["ELITZE_WEBHOOK_SECRET"] = "test-secret"
os.environ["ELITZE_ENV"] = "test"

from elitze.app import Engine  # noqa: E402


@pytest.fixture()
def engine() -> Engine:
    """A fresh Engine on an isolated SQLite database."""
    from elitze.config import fresh_settings

    with tempfile.TemporaryDirectory() as tmp:
        settings = fresh_settings(
            env="test",
            database_url=f"sqlite:///{tmp}/test.db",
            data_dir=Path(tmp) / "data",
            vault_dir=Path(tmp) / "vault",
            webhook_secret="test-secret",
            llm_backend="dry",
        )
        eng = Engine(settings)
        yield eng
        eng.shutdown()
