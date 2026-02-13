from rlm_mcp.server import build_mcp_app


def test_build_mcp_app_constructs_without_annotation_errors():
    app = build_mcp_app()
    assert app is not None
