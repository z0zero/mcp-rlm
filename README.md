# RLM MCP Codex Companion

MVP MCP server for RLM-style stateful orchestration with Codex.

## MCP Tools

- init_context
- run_repl
- get_var
- finalize
- get_trace

## Guardrails

- max_steps
- max_runtime_ms
- budget_limit

## Running Tests

```bash
. .venv/bin/activate
PYTHONPATH=src pytest -v
```
