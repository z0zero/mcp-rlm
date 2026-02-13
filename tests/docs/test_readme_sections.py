from pathlib import Path


def test_readme_has_required_sections():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "## MCP Tools" in text
    assert "## Guardrails" in text
    assert "## Running Tests" in text
