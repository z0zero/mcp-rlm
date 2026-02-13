from rlm_mcp.service import RlmMcpService


def test_finalize_with_final_text():
    svc = RlmMcpService()
    sid = svc.init_context("ctx")
    out = svc.finalize(sid, final_text="done")
    assert out["final_answer"] == "done"
    assert out["finish_reason"] == "completed"


def test_get_trace_returns_list():
    svc = RlmMcpService()
    sid = svc.init_context("ctx")
    trace = svc.get_trace(sid)
    assert isinstance(trace, list)
