from __future__ import annotations

import time

from rlm_mcp.session_store import SessionState


class GuardrailController:
    def should_stop(self, session: SessionState) -> tuple[bool, str | None]:
        if session.step_index >= session.config.max_steps:
            return True, "max_steps"

        elapsed_ms = int((time.monotonic() - session.started_at) * 1000)
        if elapsed_ms >= session.config.max_runtime_ms:
            return True, "timeout"

        if session.budget_used >= session.config.budget_limit:
            return True, "budget_exceeded"

        return False, None
