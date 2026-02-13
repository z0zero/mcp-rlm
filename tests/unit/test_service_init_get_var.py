from rlm_mcp.models import SessionConfig
from rlm_mcp.service import RlmMcpService


def test_init_context_creates_session_and_get_var_reads_context():
    svc = RlmMcpService()
    sid = svc.init_context("hello", SessionConfig())
    val = svc.get_var(sid, "context")
    assert val["value"] == "hello"
