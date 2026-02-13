import pytest

from rlm_mcp.errors import RlmMcpError
from rlm_mcp.models import SessionConfig
from rlm_mcp.session_store import InMemorySessionStore


def test_create_and_read_session_context():
    store = InMemorySessionStore()
    sid = store.create_session("long context", SessionConfig())
    session = store.get_session(sid)
    assert session.context_text == "long context"


def test_missing_session_raises():
    store = InMemorySessionStore()
    with pytest.raises(RlmMcpError):
        store.get_session("missing")
