from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from rlm_mcp.errors import ErrorCode, RlmMcpError
from rlm_mcp.models import SessionConfig


@dataclass
class SessionState:
    session_id: str
    context_text: str
    config: SessionConfig
    vars: dict[str, Any] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.monotonic)
    started_at: float = field(default_factory=time.monotonic)
    step_index: int = 0
    budget_used: int = 0
    finish_reason: str | None = None
    status: str = "active"


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def create_session(self, context_text: str, config: SessionConfig) -> str:
        session_id = str(uuid4())
        self._sessions[session_id] = SessionState(
            session_id=session_id,
            context_text=context_text,
            config=config,
        )
        return session_id

    def get_session(self, session_id: str) -> SessionState:
        session = self._sessions.get(session_id)
        if session is None:
            raise RlmMcpError(ErrorCode.SESSION_NOT_FOUND, f"session not found: {session_id}")
        return session
