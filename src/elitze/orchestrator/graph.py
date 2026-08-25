"""LangGraph assembly of the revenue experimentation loop."""

from __future__ import annotations

import functools
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import (
    NodeContext,
    budget,
    discover,
    evaluate,
    execute,
    finalize,
    improve,
    measure,
    model,
    promote_kill,
    qualify,
    reinvest,
    test,
)
from .state import LoopState


def _should_improve(state: LoopState) -> str:
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)
    exp = state.get("experiment") or {}
    evaluation = exp.get("evaluation") or {}
    if iteration < max_iterations and evaluation.get("should_improve"):
        return "improve"
    return "promote_kill"


def _should_iterate(state: LoopState) -> str:
    """Re-execute only for *free* paper benchmarking.

    In REAL mode a single run executes exactly once (real spend); recursive
    optimization is performed on paper so no money is double-spent. New
    real versions are run as their own budgeted experiment.
    """
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)
    if state.get("simulated") and iteration < max_iterations:
        return "execute"
    return "promote_kill"


def build_graph(ctx: NodeContext, checkpointer: Any | None = None) -> Any:
    """Build a compiled LangGraph for the core loop.

    ``checkpointer`` defaults to :class:`MemorySaver` so long-running loops
    can checkpoint state in-process.
    """
    graph = StateGraph(LoopState)

    node = functools.partial
    graph.add_node("discover", node(discover, ctx=ctx))
    graph.add_node("qualify", node(qualify, ctx=ctx))
    graph.add_node("model", node(model, ctx=ctx))
    graph.add_node("budget", node(budget, ctx=ctx))
    graph.add_node("execute", node(execute, ctx=ctx))
    graph.add_node("measure", node(measure, ctx=ctx))
    graph.add_node("evaluate", node(evaluate, ctx=ctx))
    graph.add_node("improve", node(improve, ctx=ctx))
    graph.add_node("test", node(test, ctx=ctx))
    graph.add_node("promote_kill", node(promote_kill, ctx=ctx))
    graph.add_node("reinvest", node(reinvest, ctx=ctx))
    graph.add_node("finalize", node(finalize, ctx=ctx))

    graph.add_edge(START, "discover")
    graph.add_edge("discover", "qualify")
    graph.add_edge("qualify", "model")
    graph.add_edge("model", "budget")
    graph.add_edge("budget", "execute")
    graph.add_edge("execute", "measure")
    graph.add_edge("measure", "evaluate")

    graph.add_conditional_edges(
        "evaluate",
        _should_improve,
        {"improve": "improve", "promote_kill": "promote_kill"},
    )
    graph.add_edge("improve", "test")
    graph.add_conditional_edges(
        "test",
        _should_iterate,
        {"execute": "execute", "promote_kill": "promote_kill"},
    )

    graph.add_edge("promote_kill", "reinvest")
    graph.add_edge("reinvest", "finalize")
    graph.add_edge("finalize", END)

    checkpointer = checkpointer if checkpointer is not None else MemorySaver()
    return graph.compile(checkpointer=checkpointer)
