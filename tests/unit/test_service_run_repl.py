from rlm_mcp.models import SessionConfig
from rlm_mcp.service import RlmMcpService


def test_run_repl_increments_step_and_updates_vars():
    svc = RlmMcpService()
    sid = svc.init_context("abc", SessionConfig(max_steps=5, max_runtime_ms=60000, budget_limit=10000))
    out = svc.run_repl(sid, "result = context.upper()")
    assert out["step_index"] == 1
    assert svc.get_var(sid, "result")["value"] == "ABC"
