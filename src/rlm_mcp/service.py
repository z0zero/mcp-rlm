from __future__ import annotations

import time
from typing import Any

from rlm_mcp.errors import ErrorCode, RlmMcpError
from rlm_mcp.guardrails import GuardrailController
from rlm_mcp.models import SessionConfig
from rlm_mcp.sandbox import SandboxExecutor
from rlm_mcp.session_store import InMemorySessionStore
from rlm_mcp.trace import TraceLogger


class RlmMcpService:
    def __init__(self) -> None:
        self.store = InMemorySessionStore()
        self.guardrails = GuardrailController()
        self.sandbox = SandboxExecutor()
        self.trace = TraceLogger()

    def init_context(self, context_text: str, config: SessionConfig | None = None) -> str:
        if not context_text:
            raise RlmMcpError(ErrorCode.INVALID_INPUT, "context_text must not be empty")

        cfg = config or SessionConfig()
        session_id = self.store.create_session(context_text, cfg)
        session = self.store.get_session(session_id)
        session.vars["context"] = context_text

        self.trace.log(
            session.trace,
            step_index=session.step_index,
            action="init_context",
            result_status="ok",
            summary="context initialized",
            guardrail_snapshot=self._guardrail_snapshot(session),
        )
        return session_id

    def run_repl(self, session_id: str, code: str) -> dict[str, Any]:
        session = self.store.get_session(session_id)

        if session.status != "active":
            return {
                "stdout": "",
                "stderr": "",
                "updated_vars_summary": sorted(session.vars.keys()),
                "step_index": session.step_index,
                "guardrail_stop": session.finish_reason,
            }

        stop, reason = self.guardrails.should_stop(session)
        if stop:
            self._stop_session(session, reason)
            return {
                "stdout": "",
                "stderr": "",
                "updated_vars_summary": sorted(session.vars.keys()),
                "step_index": session.step_index,
                "guardrail_stop": reason,
            }

        result = self.sandbox.run(code, session.vars)
        session.step_index += 1
        session.budget_used += len(code) + len(result.stdout) + len(result.stderr)

        status = "error" if result.error else "ok"
        self.trace.log(
            session.trace,
            step_index=session.step_index,
            action="run_repl",
            result_status=status,
            summary=(code[:120] + "...") if len(code) > 120 else code,
            guardrail_snapshot=self._guardrail_snapshot(session),
        )

        stop, reason = self.guardrails.should_stop(session)
        if stop:
            self._stop_session(session, reason)

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "updated_vars_summary": sorted(session.vars.keys()),
            "step_index": session.step_index,
            "guardrail_stop": reason if stop else None,
        }

    def get_var(self, session_id: str, var_name: str) -> dict[str, Any]:
        session = self.store.get_session(session_id)
        value = session.vars.get(var_name)
        serialized, truncated = self._serialize_value(value)
        return {
            "value": serialized,
            "type": type(value).__name__ if value is not None else "NoneType",
            "truncated": truncated,
        }

    def finalize(
        self,
        session_id: str,
        *,
        final_text: str | None = None,
        final_var_name: str | None = None,
    ) -> dict[str, Any]:
        session = self.store.get_session(session_id)

        if final_text is None and final_var_name is None:
            raise RlmMcpError(
                ErrorCode.INVALID_INPUT,
                "either final_text or final_var_name must be provided",
            )

        if final_text is not None:
            answer = final_text
        else:
            answer = str(session.vars.get(final_var_name, ""))

        session.status = "finalized"
        if session.finish_reason is None:
            session.finish_reason = "completed"

        self.trace.log(
            session.trace,
            step_index=session.step_index,
            action="finalize",
            result_status="ok",
            summary="session finalized",
            guardrail_snapshot=self._guardrail_snapshot(session),
        )

        return {
            "final_answer": answer,
            "finish_reason": session.finish_reason,
            "stats": {
                "steps": session.step_index,
                "runtime_ms": int((time.monotonic() - session.started_at) * 1000),
                "budget_used": session.budget_used,
            },
        }

    def get_trace(
        self,
        session_id: str,
        *,
        from_step: int | None = None,
        to_step: int | None = None,
    ) -> list[dict[str, Any]]:
        session = self.store.get_session(session_id)
        events = session.trace
        if from_step is not None:
            events = [e for e in events if e["step_index"] >= from_step]
        if to_step is not None:
            events = [e for e in events if e["step_index"] <= to_step]
        return events

    @staticmethod
    def _serialize_value(value: Any, max_chars: int = 4000) -> tuple[Any, bool]:
        if isinstance(value, (str, int, float, bool, list, dict, tuple, set)) or value is None:
            data = value
        else:
            data = repr(value)

        rendered = str(data)
        if len(rendered) > max_chars:
            return rendered[:max_chars], True
        return data, False

    def _stop_session(self, session: Any, reason: str | None) -> None:
        session.status = "stopped"
        session.finish_reason = reason

    def _guardrail_snapshot(self, session: Any) -> dict[str, Any]:
        return {
            "step_index": session.step_index,
            "max_steps": session.config.max_steps,
            "budget_used": session.budget_used,
            "budget_limit": session.config.budget_limit,
        }
