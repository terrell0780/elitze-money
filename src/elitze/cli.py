"""Command-line interface (Typer)."""

from __future__ import annotations

import json
from decimal import Decimal

import typer

from . import __version__
from .app import Engine
from .config import get_settings
from .domain.enums import EngineType, ExecutionMode, ExperimentStatus
from .domain.models import Experiment

app = typer.Typer(
    name="elitze",
    help="Elitze Money Engine — autonomous revenue experimentation platform.",
    no_args_is_help=True,
)

_engine_opt = typer.Option(None, "--engine", "-e", help="Revenue engine to run.")


def _engine() -> Engine:
    settings = get_settings()
    settings.resolve_paths()
    return Engine(settings)


def _print_experiment(exp: Experiment) -> None:
    typer.echo(json.dumps(exp.model_dump(mode="json"), indent=2, default=str))


@app.callback(invoke_without_command=True)
def _version_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
) -> None:
    if version:
        typer.echo(f"elitze {__version__}")
        raise typer.Exit()


@app.command()
def run(
    engine: EngineType = typer.Argument(..., help="Revenue engine to run."),
    title: str = typer.Option("Untitled experiment", "--title", "-t", help="Experiment title."),
    paper: bool = typer.Option(False, "--paper", help="Run a labeled paper (simulation) instead of a real run."),
    thesis: str | None = typer.Option(None, "--thesis", help="Override the experiment thesis."),
    rollback: str = typer.Option("", "--rollback", help="Mandatory rollback plan for real promotion."),
    iterations: int | None = typer.Option(None, "--iterations", help="Override max improvement iterations."),
) -> None:
    """Run one experiment through the full loop."""
    eng = _engine()
    if iterations is not None:
        eng._ctx.max_iterations = iterations  # noqa: SLF001
    mode = ExecutionMode.PAPER if paper else ExecutionMode.REAL
    exp = eng.run_experiment(
        engine,
        title,
        mode=mode,
        thesis=thesis,
        rollback_plan=rollback,
    )
    typer.echo(f"Experiment {exp.id} finished: {exp.status.value}")
    _print_experiment(exp)
    eng.shutdown()


@app.command("list")
def list_experiments(
    status: ExperimentStatus | None = typer.Option(None, "--status", help="Filter by status."),
    engine: EngineType | None = typer.Option(None, "--engine", "-e", help="Filter by engine."),
    limit: int = typer.Option(50, "--limit", help="Max results."),
) -> None:
    """List persisted experiments."""
    eng = _engine()
    for exp in eng.list_experiments(status=status, engine=engine, limit=limit):
        typer.echo(
            f"{exp.id[:8]}  {exp.status.value:<12} {exp.engine.value:<22} "
            f"roi={exp.roi} profit={exp.profit}  {exp.title}"
        )
    eng.shutdown()


@app.command()
def show(experiment_id: str = typer.Argument(..., help="Experiment ID.")) -> None:
    """Show a single experiment in full."""
    eng = _engine()
    exp = eng.get_experiment(experiment_id)
    if exp is None:
        typer.echo(f"experiment {experiment_id} not found", err=True)
        raise typer.Exit(1)
    _print_experiment(exp)
    eng.shutdown()


@app.command()
def pool() -> None:
    """Show the reinvestment pool balance."""
    eng = _engine()
    typer.echo(f"pool balance: {eng.pool_balance()} {eng.settings.default_currency}")
    typer.echo(f"verified revenue: {eng.verified_revenue()} {eng.settings.default_currency}")
    eng.shutdown()


@app.command()
def seed(amount: str = typer.Argument(..., help="Amount to add to the pool.")) -> None:
    """Seed the reinvestment pool with verified capital (operator action)."""
    eng = _engine()
    value = Decimal(amount)
    eng.seed_pool(value)
    typer.echo(f"seeded {value} {eng.settings.default_currency}; pool now {eng.pool_balance()}")
    eng.shutdown()


@app.command()
def agents() -> None:
    """List registered agents."""
    eng = _engine()
    for agent in eng.repo.list_agents():
        typer.echo(f"{agent.name:<24} {agent.status.value:<10} engine={agent.engine.value if agent.engine else '-'}")
    eng.shutdown()


@app.command()
def serve(
    host: str | None = typer.Option(None, "--host", help="Bind host."),
    port: int | None = typer.Option(None, "--port", help="Bind port."),
) -> None:
    """Run the HTTP API (uvicorn)."""
    import uvicorn

    settings = get_settings()
    settings.resolve_paths()
    uvicorn.run(
        "elitze.api:create_app",
        factory=True,
        host=host or settings.api_host,
        port=port or settings.api_port,
    )


if __name__ == "__main__":
    app()
