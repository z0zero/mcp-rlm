from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class TraceLogger:
    def log(
        self,
        events: list[dict[str, Any]],
        *,
        step_index: int,
        action: str,
        result_status: str,
        summary: str,
        guardrail_snapshot: dict[str, Any] | None = None,
    ) -> None:
        events.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "step_index": step_index,
                "action": action,
                "result_status": result_status,
                "summary": summary,
                "guardrail_snapshot": guardrail_snapshot or {},
            }
        )
