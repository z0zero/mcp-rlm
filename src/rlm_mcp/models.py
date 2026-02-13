from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SessionConfig:
    max_steps: int = 64
    max_runtime_ms: int = 120_000
    budget_limit: int = 100_000

    def __post_init__(self) -> None:
        if self.max_steps <= 0:
            raise ValueError("max_steps must be > 0")
        if self.max_runtime_ms <= 0:
            raise ValueError("max_runtime_ms must be > 0")
        if self.budget_limit <= 0:
            raise ValueError("budget_limit must be > 0")
