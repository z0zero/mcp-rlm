from __future__ import annotations

import json
from enum import Enum
from typing import Any, Callable

from rlm_mcp.errors import RlmMcpError
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
        # Preferred names with service prefix.
        "rlm_init_context": server.init_context,
        "rlm_run_repl": server.run_repl,
        "rlm_get_var": server.get_var,
        "rlm_finalize": server.finalize,
        "rlm_get_trace": server.get_trace,
        # Backward-compat aliases.
        "init_context": server.init_context,
        "run_repl": server.run_repl,
        "get_var": server.get_var,
        "finalize": server.finalize,
        "get_trace": server.get_trace,
    }


class ResponseFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"


def _as_markdown(data: Any) -> str:
    if isinstance(data, str):
        return data
    return "```json\n" + json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n```"


def _tool_success(data: Any, response_format: ResponseFormat = ResponseFormat.JSON) -> dict[str, Any]:
    if response_format == ResponseFormat.MARKDOWN:
        return {
            "ok": True,
            "format": response_format.value,
            "markdown": _as_markdown(data),
            "data": data,
        }
    return {"ok": True, "format": response_format.value, "data": data}


def _tool_error(exc: Exception, response_format: ResponseFormat = ResponseFormat.JSON) -> dict[str, Any]:
    error_payload: dict[str, Any]
    if isinstance(exc, RlmMcpError):
        error_payload = {
            "code": exc.code.value,
            "message": exc.message,
            "next_step": "Check input values (session_id, context_text, or finalize payload) and retry.",
        }
    else:
        error_payload = {
            "code": "INTERNAL_ERROR",
            "message": f"{type(exc).__name__}: {exc}",
            "next_step": "Inspect server logs and retry with smaller/simpler payload.",
        }

    if response_format == ResponseFormat.MARKDOWN:
        md = (
            f"### Error `{error_payload['code']}`\n\n"
            f"{error_payload['message']}\n\n"
            f"Next step: {error_payload['next_step']}"
        )
        return {
            "ok": False,
            "format": response_format.value,
            "markdown": md,
            "error": error_payload,
        }

    return {"ok": False, "format": response_format.value, "error": error_payload}


def build_mcp_app(service: RlmMcpService | None = None) -> Any:
    """Build FastMCP app lazily so non-MCP tests can run without SDK installed."""
    try:
        from mcp.server.fastmcp import FastMCP
        from pydantic import BaseModel, ConfigDict, Field, model_validator
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "MCP SDK is not installed. Install dependencies first: `python -m pip install -e .`."
        ) from exc

    class InitContextInput(BaseModel):
        model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

        context_text: str = Field(..., min_length=1, description="Long context to load into in-memory session state.")
        max_steps: int = Field(default=64, ge=1, le=10_000)
        max_runtime_ms: int = Field(default=120_000, ge=1_000, le=3_600_000)
        budget_limit: int = Field(default=100_000, ge=1_000, le=10_000_000)
        response_format: ResponseFormat = Field(default=ResponseFormat.JSON)

    class RunReplInput(BaseModel):
        model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

        session_id: str = Field(..., min_length=1, description="Session id from rlm_init_context.")
        code: str = Field(..., min_length=1, max_length=50_000, description="Python code snippet to execute.")
        response_format: ResponseFormat = Field(default=ResponseFormat.JSON)

    class GetVarInput(BaseModel):
        model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

        session_id: str = Field(..., min_length=1)
        var_name: str = Field(..., min_length=1, max_length=256)
        response_format: ResponseFormat = Field(default=ResponseFormat.JSON)

    class FinalizeInput(BaseModel):
        model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

        session_id: str = Field(..., min_length=1)
        final_text: str | None = Field(default=None)
        final_var_name: str | None = Field(default=None, min_length=1, max_length=256)
        response_format: ResponseFormat = Field(default=ResponseFormat.JSON)

        @model_validator(mode="after")
        def validate_finalize_payload(self) -> "FinalizeInput":
            if self.final_text is None and self.final_var_name is None:
                raise ValueError("either final_text or final_var_name must be provided")
            return self

    class GetTraceInput(BaseModel):
        model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

        session_id: str = Field(..., min_length=1)
        from_step: int | None = Field(default=None, ge=0)
        to_step: int | None = Field(default=None, ge=0)
        response_format: ResponseFormat = Field(default=ResponseFormat.JSON)

    server = RlmMcpServer(service)
    mcp = FastMCP("rlm_mcp")

    @mcp.tool(
        name="rlm_init_context",
        annotations={
            "title": "Initialize RLM Context",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    def rlm_init_context(params: InitContextInput) -> dict[str, Any]:
        """Create a new in-memory RLM session and load long context."""
        try:
            payload = server.init_context(
                context_text=params.context_text,
                session_config={
                    "max_steps": params.max_steps,
                    "max_runtime_ms": params.max_runtime_ms,
                    "budget_limit": params.budget_limit,
                },
            )
            return _tool_success(payload, response_format=params.response_format)
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc, response_format=params.response_format)

    @mcp.tool(
        name="rlm_run_repl",
        annotations={
            "title": "Run REPL Step",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    def rlm_run_repl(params: RunReplInput) -> dict[str, Any]:
        """Execute Python snippet against session environment with guardrails."""
        try:
            data = server.run_repl(session_id=params.session_id, code=params.code)
            return _tool_success(data, response_format=params.response_format)
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc, response_format=params.response_format)

    @mcp.tool(
        name="rlm_get_var",
        annotations={
            "title": "Read Session Variable",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def rlm_get_var(params: GetVarInput) -> dict[str, Any]:
        """Read one variable from session state."""
        try:
            data = server.get_var(session_id=params.session_id, var_name=params.var_name)
            return _tool_success(data, response_format=params.response_format)
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc, response_format=params.response_format)

    @mcp.tool(
        name="rlm_finalize",
        annotations={
            "title": "Finalize Session",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def rlm_finalize(params: FinalizeInput) -> dict[str, Any]:
        """Finalize a session using direct text or a variable name."""
        try:
            data = server.finalize(
                session_id=params.session_id,
                final_text=params.final_text,
                final_var_name=params.final_var_name,
            )
            return _tool_success(data, response_format=params.response_format)
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc, response_format=params.response_format)

    @mcp.tool(
        name="rlm_get_trace",
        annotations={
            "title": "Get Session Trace",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def rlm_get_trace(params: GetTraceInput) -> dict[str, Any]:
        """Return trace events for debugging recursive trajectories."""
        try:
            data = server.get_trace(
                session_id=params.session_id,
                from_step=params.from_step,
                to_step=params.to_step,
            )
            return _tool_success(data, response_format=params.response_format)
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc, response_format=params.response_format)

    return mcp


def main() -> None:
    app = build_mcp_app()
    app.run()


if __name__ == "__main__":
    main()
