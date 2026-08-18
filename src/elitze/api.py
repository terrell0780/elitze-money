"""HTTP API (FastAPI).

Exposes experiment orchestration, the reinvestment pool, and the verified
revenue webhook. Revenue is accepted only through the signed webhook path.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .app import Engine
from .config import get_settings
from .domain.enums import EngineType, ExecutionMode, ExperimentStatus
from .domain.errors import ElitzeError, RevenueVerificationError
from .domain.models import Experiment


class RunRequest(BaseModel):
    engine: EngineType
    title: str = "Untitled experiment"
    mode: ExecutionMode = ExecutionMode.REAL
    thesis: str | None = None
    rollback_plan: str = ""
    iterations: int | None = Field(default=None, ge=1, le=20)


class SeedRequest(BaseModel):
    amount: Decimal = Field(gt=0)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Elitze Money Engine",
        version="0.1.0",
        description="Production-oriented autonomous revenue experimentation platform.",
    )
    engine = _build_engine()
    app.state.engine = engine

    dashboard_path = Path(__file__).parent / "web" / "dashboard.html"

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(dashboard_path, media_type="text/html")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "llm_backend": engine.llm.backend_name}

    @app.get("/experiments")
    def list_experiments(
        status: ExperimentStatus | None = None,
        engine_type: EngineType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Experiment]:
        return engine.list_experiments(status=status, engine=engine_type, limit=limit, offset=offset)

    @app.get("/experiments/{experiment_id}")
    def get_experiment(experiment_id: str) -> Experiment:
        exp = engine.get_experiment(experiment_id)
        if exp is None:
            raise HTTPException(status_code=404, detail="experiment not found")
        return exp

    @app.post("/experiments/run")
    def run_experiment(body: RunRequest) -> Experiment:
        if body.iterations is not None:
            engine._ctx.max_iterations = body.iterations  # noqa: SLF001
        try:
            return engine.run_experiment(
                body.engine,
                body.title,
                mode=body.mode,
                thesis=body.thesis,
                rollback_plan=body.rollback_plan,
            )
        except ElitzeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/pool")
    def pool() -> dict[str, Any]:
        return {
            "balance": str(engine.pool_balance()),
            "verified_revenue": str(engine.verified_revenue()),
            "currency": engine.settings.default_currency,
        }

    @app.post("/pool/seed")
    def seed_pool(body: SeedRequest) -> dict[str, Any]:
        engine.seed_pool(body.amount)
        return {"balance": str(engine.pool_balance())}

    @app.get("/agents")
    def agents() -> list[Any]:
        return engine.repo.list_agents()

    @app.post("/revenue/webhook/{provider}")
    async def revenue_webhook(
        provider: str,
        request: Request,
        x_hub_signature_256: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """Verified revenue webhook.

        Requires an HMAC-SHA256 signature of the raw body and a payload with
        ``event_id``, ``experiment_id``, ``amount``, and ``currency``.
        """
        body = await request.body()
        try:
            payload = await request.json()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="invalid JSON body") from exc

        try:
            ingested = engine.ingest_revenue(
                provider=provider,
                event_id=str(payload.get("event_id", "")),
                experiment_id=str(payload.get("experiment_id", "")),
                amount=Decimal(str(payload.get("amount", "0"))),
                currency=str(payload.get("currency", engine.settings.default_currency)),
                body=body,
                signature=x_hub_signature_256,
                payload=payload,
            )
        except RevenueVerificationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        return {
            "accepted": True,
            "duplicate": ingested.duplicate,
            "entry_id": ingested.entry.id,
            "amount": str(ingested.entry.amount),
        }

    return app


def _build_engine() -> Engine:
    settings = get_settings()
    settings.resolve_paths()
    return Engine(settings)
