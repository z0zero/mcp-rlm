from rlm_mcp.service import RlmMcpService


def test_end_to_end_loop_with_recursive_pattern_and_finalize():
    svc = RlmMcpService()
    sid = svc.init_context("alpha beta gamma")

    # simulate recursive/chunk-like steps from Codex
    svc.run_repl(sid, "chunks = context.split()")
    svc.run_repl(sid, "agg = [c.upper() for c in chunks]")
    svc.run_repl(sid, "final_text = ' '.join(agg)")

    out = svc.finalize(sid, final_var_name="final_text")
    assert out["final_answer"] == "ALPHA BETA GAMMA"
    assert out["finish_reason"] in {"completed", "max_steps", "timeout", "budget_exceeded"}
