"""Policy guardrails.

Enforces the README safety boundary before any experiment is executed or
promoted. Actions outside the boundary are denied with an auditable reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..domain.enums import PolicyDecision
from ..log import get_logger

log = get_logger("policy")


@dataclass(frozen=True)
class SafetyBoundary:
    """Disallowed activity patterns (README: Safety Boundary)."""

    denied_terms: tuple[str, ...] = (
        "fraud",
        "credential theft",
        "steal credentials",
        "phishing",
        "malware",
        "ransomware",
        "botnet",
        "unauthorized access",
        "hack into",
        "exploit vulnerability to breach",
        "spam",
        "platform-control evasion",
        "ban evasion",
        "identity theft",
        "market manipulation",
        "pump and dump",
        "insider trading",
        "money laundering",
        "dark web",
        "counterfeit",
    )


@dataclass
class PolicyResult:
    decision: PolicyDecision
    rule: str
    detail: str
    denied_terms: list[str] = field(default_factory=list)


class PolicyEngine:
    """Checks text, spend, and promotion actions against the boundary."""

    def __init__(self, boundary: SafetyBoundary | None = None) -> None:
        self.boundary = boundary or SafetyBoundary()

    def evaluate_text(self, text: str) -> PolicyResult:
        lowered = text.lower()
        hits = [t for t in self.boundary.denied_terms if t in lowered]
        if hits:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                rule="safety_boundary",
                detail=f"content matches disallowed activity: {', '.join(hits)}",
                denied_terms=hits,
            )
        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            rule="safety_boundary",
            detail="content within safety boundary",
        )

    def evaluate_budget(self, amount, max_budget) -> PolicyResult:
        if amount > max_budget:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                rule="budget_cap",
                detail=f"amount {amount} exceeds cap {max_budget}",
            )
        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            rule="budget_cap",
            detail=f"amount {amount} within cap {max_budget}",
        )

    def evaluate_promotion(self, *, simulated: bool, has_rollback: bool,
                           promotion_text: str = "") -> PolicyResult:
        text_result = self.evaluate_text(promotion_text)
        if text_result.decision == PolicyDecision.DENY:
            return text_result
        if simulated:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                rule="no_promote_simulation",
                detail="simulated results cannot be promoted as real revenue",
            )
        if not has_rollback:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                rule="rollback_required",
                detail="production changes require a rollback plan",
            )
        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            rule="promotion_gate",
            detail="promotion allowed (real results + rollback plan)",
        )

    def evaluate_candidate(self, title: str, thesis: str) -> PolicyResult:
        return self.evaluate_text(f"{title}\n{thesis}")

    @staticmethod
    def looks_like_secret(text: str) -> bool:
        """Heuristic: detect obvious credential material in generated output."""
        patterns = (
            r"(?i)api[_-]?key\s*[:=]\s*\S{8,}",
            r"(?i)secret\s*[:=]\s*\S{8,}",
            r"(?i)password\s*[:=]\s*\S{6,}",
            r"(?i)bearer\s+[A-Za-z0-9_\-\.]{16,}",
        )
        return any(re.search(p, text) for p in patterns)
