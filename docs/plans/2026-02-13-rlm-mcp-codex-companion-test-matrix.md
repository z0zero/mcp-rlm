# RLM MCP Codex Companion MVP Test Matrix

## Unit

- models and errors contract
- in-memory session store
- guardrail controller (`max_steps`, `timeout`, `budget_exceeded`)
- trace logger
- sandbox execution
- service init/get_var
- service run_repl
- service finalize/get_trace

## Integration

- end-to-end recursive/chunk-like flow and finalize
- guardrail stop behavior propagation

## Docs

- README includes MCP tools, guardrails, and test run section
