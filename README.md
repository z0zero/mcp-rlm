# RLM MCP Codex Companion

MVP MCP server for RLM-style stateful orchestration with Codex.

## MCP Tools

- rlm_init_context
- rlm_run_repl
- rlm_get_var
- rlm_finalize
- rlm_get_trace

## Guardrails

- max_steps
- max_runtime_ms
- budget_limit

## Run As MCP Server (stdio)

```bash
. .venv/bin/activate
python -m pip install -e .
python -m rlm_mcp.server
```

## Running Tests

```bash
. .venv/bin/activate
PYTHONPATH=src pytest -v
```
