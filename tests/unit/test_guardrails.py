import time

from rlm_mcp.guardrails import GuardrailController
from rlm_mcp.models import SessionConfig
from rlm_mcp.session_store import SessionState


def test_stops_when_max_steps_exceeded():
    cfg = SessionConfig(max_steps=1, max_runtime_ms=1000, budget_limit=1000)
    session = SessionState(session_id="s", context_text="c", config=cfg, step_index=1)
    controller = GuardrailController()
    stop, reason = controller.should_stop(session)
    assert stop is True
    assert reason == "max_steps"


def test_stops_when_timeout_exceeded():
    cfg = SessionConfig(max_steps=10, max_runtime_ms=1, budget_limit=1000)
    session = SessionState(session_id="s", context_text="c", config=cfg)
    session.started_at = time.monotonic() - 1
    controller = GuardrailController()
    stop, reason = controller.should_stop(session)
    assert stop is True
    assert reason == "timeout"


def test_stops_when_budget_exceeded():
    cfg = SessionConfig(max_steps=10, max_runtime_ms=1000, budget_limit=5)
    session = SessionState(session_id="s", context_text="c", config=cfg, budget_used=6)
    controller = GuardrailController()
    stop, reason = controller.should_stop(session)
    assert stop is True
    assert reason == "budget_exceeded"
