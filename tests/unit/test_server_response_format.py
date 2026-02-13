from rlm_mcp.server import ResponseFormat, _tool_error, _tool_success


def test_tool_success_json_format():
    out = _tool_success({"x": 1}, response_format=ResponseFormat.JSON)
    assert out["ok"] is True
    assert out["format"] == "json"
    assert out["data"] == {"x": 1}


def test_tool_success_markdown_format_contains_rendered_payload():
    out = _tool_success({"x": 1}, response_format=ResponseFormat.MARKDOWN)
    assert out["ok"] is True
    assert out["format"] == "markdown"
    assert "```json" in out["markdown"]
    assert '"x": 1' in out["markdown"]


def test_tool_error_markdown_format_contains_next_step():
    out = _tool_error(ValueError("boom"), response_format=ResponseFormat.MARKDOWN)
    assert out["ok"] is False
    assert out["format"] == "markdown"
    assert "Next step:" in out["markdown"]
