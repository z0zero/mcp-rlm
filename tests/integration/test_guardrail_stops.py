from rlm_mcp.models import SessionConfig
from rlm_mcp.service import RlmMcpService


def test_stops_on_max_steps():
    svc = RlmMcpService()
    sid = svc.init_context("x", SessionConfig(max_steps=1, max_runtime_ms=60000, budget_limit=99999))
    svc.run_repl(sid, "a = 1")
    out = svc.run_repl(sid, "b = 2")
    assert out["guardrail_stop"] == "max_steps"
