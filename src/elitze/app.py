"""Application service container.

Wires settings, storage, ledger, vector memory, vault, model, policy, engines,
agents, and the compiled LangGraph into a single :class:`Engine` facade used by
the CLI, the API, and the test suite.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .agents import AgentRuntime
from .config import Settings, fresh_settings
from .domain.enums import EngineType, ExecutionMode, ExperimentStatus
from .domain.models import Experiment, ExperimentModel, Strategy
from .engines.base import EngineRegistry
from .engines.base import registry as global_registry
from .knowledge import Vault
from .ledger import Ledger
from .llm import get_llm
from .log import get_logger
from .orchestrator import build_graph
from .orchestrator.nodes import NodeContext
from .orchestrator.state import LoopState
from .policy import PolicyEngine
from .storage.db import Database
from .storage.repository import Repository
from .storage.vector import make_vector_store

log = get_logger("app")


class Engine:
    """The Elitze Money Engine."""

    def __init__(self, settings: Settings | None = None, registry: EngineRegistry | None = None) -> None:
        self.settings = settings or fresh_settings()
        self.settings.resolve_paths()

        self.db = Database(self.settings)
        self.db.create_all()

        self.repo = Repository(self.db)
        self.ledger = Ledger(self.repo)
        self.vector = make_vector_store(self.settings)
        self.vault = Vault(self.settings.vault_dir)
        self.llm = get_llm(self.settings)
        self.policy = PolicyEngine()
        self.registry = registry or global_registry
        self.agents = AgentRuntime(self.repo)

        self._ctx = NodeContext(
            settings=self.settings,
            llm=self.llm,
            policy=self.policy,
            repo=self.repo,
            ledger=self.ledger,
            vault=self.vault,
            vector=self.vector,
            registry=self.registry,
            max_iterations=self.settings.max_iterations,
        )
        self._graph = build_graph(self._ctx)

    # ------------------------------------------------------------------ #
    def run_experiment(
        self,
        engine: EngineType,
        title: str,
        *,
        mode: ExecutionMode = ExecutionMode.REAL,
        strategy_id: str | None = None,
        parent_strategy: str | None = None,
        rollback_plan: str = "",
        thesis: str | None = None,
    ) -> Experiment:
        """Run the full DISCOVER→REINVEST loop and persist the result."""
        experiment = self._new_experiment(
            engine=engine,
            title=title,
            mode=mode,
            strategy_id=strategy_id,
            parent_strategy=parent_strategy,
            rollback_plan=rollback_plan,
            thesis=thesis,
        )
        initial: LoopState = {
            "experiment_id": experiment.id,
            "experiment": experiment.model_dump(mode="json"),
            "iteration": 0,
            "max_iterations": self.settings.max_iterations,
            "promote": False,
            "kill": False,
            "reinvest": False,
            "budget_approved": False,
            "simulated": mode != ExecutionMode.REAL,
            "errors": [],
            "notes": [],
        }
        result = self._graph.invoke(
            initial, config={"configurable": {"thread_id": experiment.id}}
        )
        return Experiment.model_validate(result["experiment"])

    def _new_experiment(
        self,
        *,
        engine: EngineType,
        title: str,
        mode: ExecutionMode,
        strategy_id: str | None,
        parent_strategy: str | None,
        rollback_plan: str,
        thesis: str | None,
    ) -> Experiment:
        version = 0
        if strategy_id is None:
            strategy_id = Strategy(name=title, engine=engine).id
        strat = self.repo.get_strategy(strategy_id)
        if strat is not None:
            version = self.repo.next_version(strat.name, engine)
        model = None
        if thesis:
            model = {
                "strategy_id": strategy_id,
                "engine": engine.value,
                "title": title,
                "thesis": thesis,
                "assumptions": {"thesis": thesis},
                "success_metrics": ["verified_revenue", "roi", "conversion_rate"],
                "stop_loss": "0.00",
                "mode": mode.value,
            }
        return Experiment(
            strategy_id=strategy_id,
            version=version,
            parent_strategy=parent_strategy,
            engine=engine,
            title=title,
            mode=mode,
            status=ExperimentStatus.DRAFT,
            rollback_plan=rollback_plan,
            model=ExperimentModel.model_validate(model) if model else None,
            tags=[engine.value],
        )

    # ------------------------------------------------------------------ #
    def get_experiment(self, experiment_id: str) -> Experiment | None:
        return self.repo.get_experiment(experiment_id)

    def reconcile_experiment(self, experiment_id: str) -> Experiment | None:
        """Recompute an experiment's finances from the verified ledger.

        Called when asynchronous revenue arrives after the loop has finished,
        so the experiment record always reflects verified truth.
        """

        exp = self.repo.get_experiment(experiment_id)
        if exp is None:
            return None
        revenue = self.ledger.verified_revenue(experiment_id)
        spend = self.ledger.spend(experiment_id)
        exp.revenue = revenue
        exp.execution_cost = spend
        exp.profit = revenue - spend
        exp.roi = ((revenue - spend) / spend * 100) if spend else None
        if exp.measurement is not None:
            exp.measurement.revenue = revenue
            exp.measurement.spend = spend
            exp.measurement.simulated = False
            exp.conversion_rate = exp.measurement.conversion_rate
        self.repo.save_experiment(exp)
        if self.vault is not None:
            self.vault.write_experiment(exp)
        return exp

    def ingest_revenue(
        self,
        *,
        provider: str,
        event_id: str,
        experiment_id: str,
        amount: Decimal,
        currency: str | None = None,
        body: bytes = b"",
        signature: str | None = None,
        payload: dict[str, Any] | None = None,
    ):
        """Verify and ingest a revenue event, then reconcile the experiment."""
        from .revenue import ingest_webhook

        ingested = ingest_webhook(
            ledger=self.ledger,
            repository=self.repo,
            secret=self.settings.webhook_secret_plain(),
            provider=provider,
            event_id=event_id,
            experiment_id=experiment_id,
            strategy_id=None,
            amount=amount,
            currency=currency or self.settings.default_currency,
            body=body,
            signature=signature,
            payload=payload or {},
        )
        if experiment_id:
            self.reconcile_experiment(experiment_id)
        return ingested

    def list_experiments(
        self,
        status: ExperimentStatus | None = None,
        engine: EngineType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Experiment]:
        return self.repo.list_experiments(status=status, engine=engine, limit=limit, offset=offset)

    def pool_balance(self) -> Decimal:
        return self.ledger.balance()

    def verified_revenue(self, experiment_id: str | None = None) -> Decimal:
        return self.ledger.verified_revenue(experiment_id)

    def seed_pool(self, amount: Decimal, currency: str | None = None, description: str = "initial capital") -> None:
        """Seed the reinvestment pool with verified capital (operator action).

        This records a verified revenue entry with a manual-verified source so
        the pool has funds to allocate; in production this arrives via
        verified revenue webhooks/integrations instead.
        """
        from .domain.enums import RevenueSource

        self.ledger.record_revenue(
            experiment_id=None,
            strategy_id=None,
            amount=amount,
            currency=currency or self.settings.default_currency,
            source=RevenueSource.MANUAL_VERIFIED,
            reference=f"seed:{self._seed_counter() or ''}",
            description=description,
        )

    _seed_n = 0

    @classmethod
    def _seed_counter(cls) -> int:
        cls._seed_n += 1
        return cls._seed_n

    def shutdown(self) -> None:
        self.agents.stop()
        self.db.dispose()
