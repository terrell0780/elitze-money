"""A persistent agent/task runtime.

Agents are registered with the repository (heartbeat + status) and can claim
and execute tasks from a durable queue. This mirrors the "OpenClaw:
persistent agent/runtime layer" from the README.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from ..domain.enums import AgentStatus, EngineType, TaskStatus
from ..domain.models import Agent, Task
from ..log import get_logger

log = get_logger("agents")

TaskHandler = Callable[[Task], dict[str, Any]]


class AgentRuntime:
    def __init__(self, repository) -> None:
        self._repo = repository
        self._handlers: dict[str, TaskHandler] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def register_agent(self, name: str, engine: EngineType | None = None) -> Agent:
        agent = Agent(name=name, engine=engine, status=AgentStatus.IDLE)
        return self._repo.upsert_agent(agent)

    def register_handler(self, kind: str, handler: TaskHandler) -> None:
        self._handlers[kind] = handler

    def submit(self, kind: str, payload: dict[str, Any], agent_id: str | None = None) -> Task:
        task = Task(kind=kind, payload=payload, agent_id=agent_id)
        return self._repo.create_task(task)

    def process_one(self) -> bool:
        """Claim and execute a single pending task. Returns True if one ran."""
        tasks = self._repo.list_pending_tasks(limit=1)
        if not tasks:
            return False
        task = tasks[0]
        handler = self._handlers.get(task.kind)
        if handler is None:
            self._repo.update_task(task.id, TaskStatus.FAILED, error=f"no handler for {task.kind}")
            return True
        self._repo.update_task(task.id, TaskStatus.RUNNING)
        try:
            result = handler(task)
            self._repo.update_task(task.id, TaskStatus.SUCCEEDED, result=result)
        except Exception as exc:  # noqa: BLE001
            log.exception("task failed", fields={"task_id": task.id})
            self._repo.update_task(task.id, TaskStatus.FAILED, error=str(exc))
        return True

    def run_forever(self, poll_seconds: float = 1.0) -> None:
        while not self._stop.is_set():
            try:
                self.process_one()
            except Exception:  # noqa: BLE001
                log.exception("agent loop error")
            self._stop.wait(poll_seconds)

    def start(self, poll_seconds: float = 1.0) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self.run_forever, kwargs={"poll_seconds": poll_seconds}, daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def heartbeat(self, name: str) -> None:
        self._repo.heartbeat(name, status=AgentStatus.RUNNING)
