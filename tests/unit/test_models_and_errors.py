from rlm_mcp.errors import ErrorCode, RlmMcpError
from rlm_mcp.models import SessionConfig


def test_default_session_config_values():
    cfg = SessionConfig()
    assert cfg.max_steps > 0
    assert cfg.max_runtime_ms > 0
    assert cfg.budget_limit > 0


def test_error_code_serialization():
    err = RlmMcpError(ErrorCode.INVALID_INPUT, "bad input")
    assert err.code.value == "INVALID_INPUT"
