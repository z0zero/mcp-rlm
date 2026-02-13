from __future__ import annotations

from typing import Any, Callable

from rlm_mcp.models import SessionConfig
from rlm_mcp.service import RlmMcpService


class RlmMcpServer:
    """Thin wrapper exposing service methods as MCP-like primitive handlers."""

    def __init__(self, service: RlmMcpService | None = None) -> None:
        self.service = service or RlmMcpService()

    def init_context(self, context_text: str, session_config: dict[str, Any] | None = None) -> dict[str, Any]:
        cfg = SessionConfig(**session_config) if session_config else SessionConfig()
        session_id = self.service.init_context(context_text, cfg)
        return {
            "session_id": session_id,
            "config": {
                "max_steps": cfg.max_steps,
                "max_runtime_ms": cfg.max_runtime_ms,
                "budget_limit": cfg.budget_limit,
            },
            "counters": {"step_index": 0, "budget_used": 0},
        }

    def run_repl(self, session_id: str, code: str) -> dict[str, Any]:
        return self.service.run_repl(session_id, code)

    def get_var(self, session_id: str, var_name: str) -> dict[str, Any]:
        return self.service.get_var(session_id, var_name)

    def finalize(
        self,
        session_id: str,
        final_text: str | None = None,
        final_var_name: str | None = None,
    ) -> dict[str, Any]:
        return self.service.finalize(session_id, final_text=final_text, final_var_name=final_var_name)

    def get_trace(self, session_id: str, from_step: int | None = None, to_step: int | None = None) -> list[dict[str, Any]]:
        return self.service.get_trace(session_id, from_step=from_step, to_step=to_step)


def create_tool_handlers(service: RlmMcpService | None = None) -> dict[str, Callable[..., Any]]:
    server = RlmMcpServer(service)
    return {
        "init_context": server.init_context,
        "run_repl": server.run_repl,
        "get_var": server.get_var,
        "finalize": server.finalize,
        "get_trace": server.get_trace,
    }
