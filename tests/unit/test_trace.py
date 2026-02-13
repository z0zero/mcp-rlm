from rlm_mcp.trace import TraceLogger


def test_trace_logger_appends_event():
    logger = TraceLogger()
    events = []
    logger.log(events, step_index=1, action="run_repl", result_status="ok", summary="did work")
    assert len(events) == 1
    assert events[0]["action"] == "run_repl"
