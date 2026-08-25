"""Knowledge vault backed by an Obsidian-style Markdown vault on disk.

Stores strategic knowledge and experiment memory as plain Markdown files that
can be opened and edited in Obsidian (frontmatter + body).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..log import get_logger

log = get_logger("knowledge")


def _frontmatter(data: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "note"


class Vault:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "strategies").mkdir(exist_ok=True)
        (self.root / "experiments").mkdir(exist_ok=True)
        (self.root / "memory").mkdir(exist_ok=True)

    # ------------------------------------------------------------------ #
    def write_strategy(self, strategy) -> Path:
        path = self.root / "strategies" / f"{_slug(strategy.name)}.md"
        body = _frontmatter(
            {
                "id": strategy.id,
                "engine": strategy.engine.value,
                "version": strategy.version,
                "parent": strategy.parent_strategy or "",
                "target_market": strategy.target_market,
                "created_at": strategy.created_at.isoformat(),
            }
        )
        body += f"\n# {strategy.name}\n\n## Thesis\n\n{strategy.thesis}\n\n"
        if strategy.config:
            body += f"## Config\n\n```json\n{strategy.config}\n```\n"
        path.write_text(body, encoding="utf-8")
        log.info("vault wrote strategy", fields={"path": str(path)})
        return path

    def write_experiment(self, experiment) -> Path:
        path = self.root / "experiments" / f"{experiment.id}.md"
        fm = {
            "id": experiment.id,
            "title": experiment.title,
            "engine": experiment.engine.value,
            "status": experiment.status.value,
            "mode": experiment.mode.value,
            "revenue": str(experiment.revenue),
            "spend": str(experiment.execution_cost),
            "profit": str(experiment.profit),
            "roi": str(experiment.roi) if experiment.roi is not None else "",
            "conversion_rate": (
                str(experiment.conversion_rate) if experiment.conversion_rate is not None else ""
            ),
            "promotion_status": experiment.promotion_status.value,
            "policy_result": experiment.policy_result.value if experiment.policy_result else "",
        }
        body = _frontmatter(fm)
        body += f"\n# {experiment.title}\n\n- **Engine:** {experiment.engine.value}\n"
        body += f"- **Status:** {experiment.status.value}\n"
        body += f"- **Promotion:** {experiment.promotion_status.value}\n\n"
        if experiment.evaluation:
            body += "## Insights\n\n"
            for insight in experiment.evaluation.insights:
                body += f"- {insight}\n"
            body += "\n"
        if experiment.decision:
            body += f"## Decision\n\n{experiment.decision.reason}\n"
            if experiment.decision.rollback_plan:
                body += f"\n**Rollback:** {experiment.decision.rollback_plan}\n"
        path.write_text(body, encoding="utf-8")
        log.info("vault wrote experiment", fields={"path": str(path)})
        return path

    def write_candidate(self, candidate) -> Path:
        path = self.root / "memory" / f"candidate-{_slug(candidate.title)}.md"
        body = _frontmatter(
            {
                "id": candidate.id,
                "engine": candidate.engine.value,
                "score": str(candidate.score),
                "status": candidate.status.value,
            }
        )
        body += f"\n# {candidate.title}\n\n{candidate.thesis}\n"
        path.write_text(body, encoding="utf-8")
        return path

    def write_note(self, name: str, content: str, tags: list[str] | None = None) -> Path:
        ts = datetime.now(UTC).isoformat()
        path = self.root / "memory" / f"{_slug(name)}.md"
        body = _frontmatter({"created_at": ts, "tags": tags or []})
        body += f"\n# {name}\n\n{content}\n"
        path.write_text(body, encoding="utf-8")
        return path
