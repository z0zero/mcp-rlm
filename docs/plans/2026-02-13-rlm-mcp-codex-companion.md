# RLM MCP Codex Companion MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python MCP server that provides primitive RLM state/sandbox tools for Codex orchestration with in-memory sessions and hard guardrails.

**Architecture:** Use a thin MCP state engine: MCP handlers call an application service composed of in-memory session store, guardrail controller, sandbox executor, and trace logger. Codex remains the reasoning orchestrator and recursively calls primitive tools (`init_context`, `run_repl`, `get_var`, `finalize`, `get_trace`).

**Tech Stack:** Python 3.11+, FastMCP (or MCP Python SDK), pytest, pydantic/dataclasses, standard library sandbox controls.

---

### Task 1: Project Scaffold and Tooling Baseline

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/rlm_mcp/__init__.py`
- Create: `src/rlm_mcp/server.py`
- Create: `tests/test_smoke_import.py`

**Step 1: Write the failing test**

```python
# tests/test_smoke_import.py

def test_package_importable():
    import rlm_mcp  # noqa: F401
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke_import.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'rlm_mcp'`

**Step 3: Write minimal implementation**

```python
# src/rlm_mcp/__init__.py
__all__ = ["__version__"]
__version__ = "0.1.0"
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_smoke_import.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add pyproject.toml README.md src/rlm_mcp/__init__.py src/rlm_mcp/server.py tests/test_smoke_import.py
git commit -m "chore: scaffold python mcp project baseline"
```

### Task 2: Domain Models and Error Contract

**Files:**
- Create: `src/rlm_mcp/models.py`
- Create: `src/rlm_mcp/errors.py`
- Test: `tests/unit/test_models_and_errors.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_models_and_errors.py
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
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_models_and_errors.py -v`  
Expected: FAIL because models/errors modules are missing.

**Step 3: Write minimal implementation**

```python
# src/rlm_mcp/errors.py
from dataclasses import dataclass
from enum import Enum


class ErrorCode(str, Enum):
    INVALID_INPUT = "INVALID_INPUT"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    GUARDRAIL_STOPPED = "GUARDRAIL_STOPPED"
    SANDBOX_EXEC_ERROR = "SANDBOX_EXEC_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass
class RlmMcpError(Exception):
    code: ErrorCode
    message: str
```

```python
# src/rlm_mcp/models.py
from dataclasses import dataclass


@dataclass
class SessionConfig:
    max_steps: int = 64
    max_runtime_ms: int = 120000
    budget_limit: int = 100000
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_models_and_errors.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/rlm_mcp/models.py src/rlm_mcp/errors.py tests/unit/test_models_and_errors.py
git commit -m "feat: add core domain models and error contract"
```

### Task 3: In-Memory Session Store

**Files:**
- Create: `src/rlm_mcp/session_store.py`
- Test: `tests/unit/test_session_store.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_session_store.py
from rlm_mcp.models import SessionConfig
from rlm_mcp.session_store import InMemorySessionStore


def test_create_and_read_session_context():
    store = InMemorySessionStore()
    sid = store.create_session("long context", SessionConfig())
    session = store.get_session(sid)
    assert session.context_text == "long context"


def test_missing_session_raises():
    store = InMemorySessionStore()
    try:
        store.get_session("missing")
        assert False
    except Exception:
        assert True
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_session_store.py -v`  
Expected: FAIL because session store is missing.

**Step 3: Write minimal implementation**

```python
# src/rlm_mcp/session_store.py
from dataclasses import dataclass, field
from uuid import uuid4

from rlm_mcp.errors import ErrorCode, RlmMcpError
from rlm_mcp.models import SessionConfig


@dataclass
class SessionState:
    session_id: str
    context_text: str
    config: SessionConfig
    vars: dict = field(default_factory=dict)
    step_index: int = 0
    budget_used: int = 0
    finish_reason: str | None = None
    status: str = "active"


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def create_session(self, context_text: str, config: SessionConfig) -> str:
        sid = str(uuid4())
        self._sessions[sid] = SessionState(session_id=sid, context_text=context_text, config=config)
        return sid

    def get_session(self, session_id: str) -> SessionState:
        session = self._sessions.get(session_id)
        if session is None:
            raise RlmMcpError(ErrorCode.SESSION_NOT_FOUND, f"session not found: {session_id}")
        return session
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_session_store.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/rlm_mcp/session_store.py tests/unit/test_session_store.py
git commit -m "feat: add in-memory session store"
```

### Task 4: Guardrail Controller (Steps, Runtime, Budget)

**Files:**
- Create: `src/rlm_mcp/guardrails.py`
- Test: `tests/unit/test_guardrails.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_guardrails.py
from rlm_mcp.guardrails import GuardrailController
from rlm_mcp.models import SessionConfig
from rlm_mcp.session_store import SessionState


def test_stops_when_max_steps_exceeded():
    cfg = SessionConfig(max_steps=1, max_runtime_ms=1000, budget_limit=1000)
    session = SessionState(session_id="s", context_text="c", config=cfg, step_index=1)
    controller = GuardrailController()
    stop, reason = controller.should_stop(session)
    assert stop is True
    assert reason == "max_steps"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_guardrails.py -v`  
Expected: FAIL because guardrail module is missing.

**Step 3: Write minimal implementation**

```python
# src/rlm_mcp/guardrails.py
import time


class GuardrailController:
    def should_stop(self, session):
        if session.step_index >= session.config.max_steps:
            return True, "max_steps"
        started_at = getattr(session, "started_at", None)
        if started_at is not None:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            if elapsed_ms >= session.config.max_runtime_ms:
                return True, "timeout"
        if session.budget_used >= session.config.budget_limit:
            return True, "budget_exceeded"
        return False, None
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_guardrails.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/rlm_mcp/guardrails.py tests/unit/test_guardrails.py
git commit -m "feat: add guardrail controller"
```

### Task 5: Trace Model and Logger

**Files:**
- Create: `src/rlm_mcp/trace.py`
- Modify: `src/rlm_mcp/session_store.py`
- Test: `tests/unit/test_trace.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_trace.py
from rlm_mcp.trace import TraceLogger


def test_trace_logger_appends_event():
    logger = TraceLogger()
    events = []
    logger.log(events, step_index=1, action="run_repl", result_status="ok", summary="did work")
    assert len(events) == 1
    assert events[0]["action"] == "run_repl"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_trace.py -v`  
Expected: FAIL because trace module is missing.

**Step 3: Write minimal implementation**

```python
# src/rlm_mcp/trace.py
from datetime import datetime, timezone


class TraceLogger:
    def log(self, events, step_index, action, result_status, summary, guardrail_snapshot=None):
        events.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "step_index": step_index,
                "action": action,
                "result_status": result_status,
                "summary": summary,
                "guardrail_snapshot": guardrail_snapshot or {},
            }
        )
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_trace.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/rlm_mcp/trace.py src/rlm_mcp/session_store.py tests/unit/test_trace.py
git commit -m "feat: add trace logging primitives"
```

### Task 6: Sandbox REPL Executor

**Files:**
- Create: `src/rlm_mcp/sandbox.py`
- Test: `tests/unit/test_sandbox.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_sandbox.py
from rlm_mcp.sandbox import SandboxExecutor


def test_exec_updates_variables_and_stdout():
    executor = SandboxExecutor()
    env = {"x": 1}
    out = executor.run("print(x)\ny = x + 1", env)
    assert "1" in out.stdout
    assert env["y"] == 2
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_sandbox.py -v`  
Expected: FAIL because sandbox module is missing.

**Step 3: Write minimal implementation**

```python
# src/rlm_mcp/sandbox.py
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass
from io import StringIO


@dataclass
class SandboxResult:
    stdout: str
    stderr: str


class SandboxExecutor:
    def run(self, code: str, env: dict) -> SandboxResult:
        stdout_buffer = StringIO()
        stderr_buffer = StringIO()
        safe_globals = {"__builtins__": {"print": print, "len": len, "range": range, "str": str, "int": int}}
        safe_globals.update(env)
        try:
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                exec(code, safe_globals, safe_globals)
        finally:
            for key, value in safe_globals.items():
                if not key.startswith("__"):
                    env[key] = value
        return SandboxResult(stdout=stdout_buffer.getvalue(), stderr=stderr_buffer.getvalue())
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_sandbox.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/rlm_mcp/sandbox.py tests/unit/test_sandbox.py
git commit -m "feat: add sandbox repl executor"
```

### Task 7: Application Service for `init_context` and `get_var`

**Files:**
- Create: `src/rlm_mcp/service.py`
- Test: `tests/unit/test_service_init_get_var.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_service_init_get_var.py
from rlm_mcp.models import SessionConfig
from rlm_mcp.service import RlmMcpService


def test_init_context_creates_session_and_get_var_reads_context():
    svc = RlmMcpService()
    sid = svc.init_context("hello", SessionConfig())
    val = svc.get_var(sid, "context")
    assert val["value"] == "hello"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_service_init_get_var.py -v`  
Expected: FAIL because service module is missing.

**Step 3: Write minimal implementation**

```python
# src/rlm_mcp/service.py
from rlm_mcp.models import SessionConfig
from rlm_mcp.session_store import InMemorySessionStore


class RlmMcpService:
    def __init__(self):
        self.store = InMemorySessionStore()

    def init_context(self, context_text: str, config: SessionConfig | None = None) -> str:
        cfg = config or SessionConfig()
        sid = self.store.create_session(context_text, cfg)
        session = self.store.get_session(sid)
        session.vars["context"] = context_text
        return sid

    def get_var(self, session_id: str, var_name: str):
        session = self.store.get_session(session_id)
        return {"value": session.vars.get(var_name), "type": type(session.vars.get(var_name)).__name__}
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_service_init_get_var.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/rlm_mcp/service.py tests/unit/test_service_init_get_var.py
git commit -m "feat: add init_context and get_var service operations"
```

### Task 8: Application Service for `run_repl` with Guardrail Integration

**Files:**
- Modify: `src/rlm_mcp/service.py`
- Modify: `src/rlm_mcp/session_store.py`
- Test: `tests/unit/test_service_run_repl.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_service_run_repl.py
from rlm_mcp.models import SessionConfig
from rlm_mcp.service import RlmMcpService


def test_run_repl_increments_step_and_updates_vars():
    svc = RlmMcpService()
    sid = svc.init_context("abc", SessionConfig(max_steps=5, max_runtime_ms=60000, budget_limit=10000))
    out = svc.run_repl(sid, "result = context.upper()")
    assert out["step_index"] == 1
    assert svc.get_var(sid, "result")["value"] == "ABC"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_service_run_repl.py -v`  
Expected: FAIL because `run_repl` is not implemented.

**Step 3: Write minimal implementation**

```python
# add into src/rlm_mcp/service.py
from rlm_mcp.guardrails import GuardrailController
from rlm_mcp.sandbox import SandboxExecutor
from rlm_mcp.trace import TraceLogger

# in __init__
self.guardrails = GuardrailController()
self.sandbox = SandboxExecutor()
self.trace = TraceLogger()

# new method
def run_repl(self, session_id: str, code: str):
    session = self.store.get_session(session_id)
    stop, reason = self.guardrails.should_stop(session)
    if stop:
        session.status = "stopped"
        session.finish_reason = reason
        return {"step_index": session.step_index, "guardrail_stop": reason}

    result = self.sandbox.run(code, session.vars)
    session.step_index += 1
    session.budget_used += len(code) + len(result.stdout) + len(result.stderr)

    self.trace.log(
        session.trace,
        step_index=session.step_index,
        action="run_repl",
        result_status="ok",
        summary="executed code",
    )

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "updated_vars_summary": sorted(list(session.vars.keys())),
        "step_index": session.step_index,
        "guardrail_stop": None,
    }
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_service_run_repl.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/rlm_mcp/service.py src/rlm_mcp/session_store.py tests/unit/test_service_run_repl.py
git commit -m "feat: implement run_repl service with guardrails and trace"
```

### Task 9: Finalization and Trace Retrieval APIs in Service

**Files:**
- Modify: `src/rlm_mcp/service.py`
- Test: `tests/unit/test_service_finalize_trace.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_service_finalize_trace.py
from rlm_mcp.service import RlmMcpService


def test_finalize_with_final_text():
    svc = RlmMcpService()
    sid = svc.init_context("ctx")
    out = svc.finalize(sid, final_text="done")
    assert out["final_answer"] == "done"
    assert out["finish_reason"] == "completed"


def test_get_trace_returns_list():
    svc = RlmMcpService()
    sid = svc.init_context("ctx")
    trace = svc.get_trace(sid)
    assert isinstance(trace, list)
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/unit/test_service_finalize_trace.py -v`  
Expected: FAIL because finalize/get_trace are missing.

**Step 3: Write minimal implementation**

```python
# add into src/rlm_mcp/service.py
import time


def finalize(self, session_id: str, final_text: str | None = None, final_var_name: str | None = None):
    session = self.store.get_session(session_id)
    if final_text is not None:
        answer = final_text
    elif final_var_name is not None:
        answer = str(session.vars.get(final_var_name, ""))
    else:
        answer = ""

    session.status = "finalized"
    if session.finish_reason is None:
        session.finish_reason = "completed"

    return {
        "final_answer": answer,
        "finish_reason": session.finish_reason,
        "stats": {
            "steps": session.step_index,
            "runtime_ms": int((time.monotonic() - session.started_at) * 1000),
            "budget_used": session.budget_used,
        },
    }


def get_trace(self, session_id: str, from_step: int | None = None, to_step: int | None = None):
    session = self.store.get_session(session_id)
    events = session.trace
    if from_step is not None:
        events = [e for e in events if e["step_index"] >= from_step]
    if to_step is not None:
        events = [e for e in events if e["step_index"] <= to_step]
    return events
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/unit/test_service_finalize_trace.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/rlm_mcp/service.py tests/unit/test_service_finalize_trace.py
git commit -m "feat: add finalize and trace retrieval operations"
```

### Task 10: MCP Tool Handlers and End-to-End Integration Test

**Files:**
- Modify: `src/rlm_mcp/server.py`
- Create: `tests/integration/test_mcp_tool_flow.py`

**Step 1: Write the failing test**

```python
# tests/integration/test_mcp_tool_flow.py
from rlm_mcp.service import RlmMcpService


def test_end_to_end_loop_with_recursive_pattern_and_finalize():
    svc = RlmMcpService()
    sid = svc.init_context("alpha beta gamma")

    # simulate recursive/chunk-like steps from Codex
    svc.run_repl(sid, "chunks = context.split()")
    svc.run_repl(sid, "agg = [c.upper() for c in chunks]")
    svc.run_repl(sid, "final_text = ' '.join(agg)")

    out = svc.finalize(sid, final_var_name="final_text")
    assert out["final_answer"] == "ALPHA BETA GAMMA"
    assert out["finish_reason"] in {"completed", "max_steps", "timeout", "budget_exceeded"}
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/integration/test_mcp_tool_flow.py -v`  
Expected: FAIL until server/service wiring is complete.

**Step 3: Write minimal implementation**

```python
# src/rlm_mcp/server.py (example outline)
from rlm_mcp.service import RlmMcpService

svc = RlmMcpService()

# register MCP tools:
# - init_context
# - run_repl
# - get_var
# - finalize
# - get_trace
# each tool calls corresponding svc method and returns JSON-serializable payload
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/integration/test_mcp_tool_flow.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/rlm_mcp/server.py tests/integration/test_mcp_tool_flow.py
git commit -m "feat: wire primitive mcp tools and e2e flow"
```

### Task 11: Guardrail Failure Mode Integration Tests

**Files:**
- Create: `tests/integration/test_guardrail_stops.py`
- Modify: `src/rlm_mcp/service.py`

**Step 1: Write the failing test**

```python
# tests/integration/test_guardrail_stops.py
from rlm_mcp.models import SessionConfig
from rlm_mcp.service import RlmMcpService


def test_stops_on_max_steps():
    svc = RlmMcpService()
    sid = svc.init_context("x", SessionConfig(max_steps=1, max_runtime_ms=60000, budget_limit=99999))
    svc.run_repl(sid, "a = 1")
    out = svc.run_repl(sid, "b = 2")
    assert out["guardrail_stop"] == "max_steps"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/integration/test_guardrail_stops.py -v`  
Expected: FAIL until stop propagation is fully consistent.

**Step 3: Write minimal implementation**

```python
# ensure run_repl always checks guardrail both before and after execution,
# and persists session.finish_reason when stop occurs.
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/integration/test_guardrail_stops.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/rlm_mcp/service.py tests/integration/test_guardrail_stops.py
git commit -m "test: enforce and verify guardrail stop behavior"
```

### Task 12: Documentation and Local Runbook

**Files:**
- Modify: `README.md`
- Create: `docs/plans/2026-02-13-rlm-mcp-codex-companion-test-matrix.md`

**Step 1: Write the failing test**

```python
# tests/docs/test_readme_sections.py
from pathlib import Path


def test_readme_has_required_sections():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "## MCP Tools" in text
    assert "## Guardrails" in text
    assert "## Running Tests" in text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/docs/test_readme_sections.py -v`  
Expected: FAIL until README is completed.

**Step 3: Write minimal implementation**

```markdown
# README.md additions
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
- PYTHONPATH=src pytest -v
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/docs/test_readme_sections.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add README.md docs/plans/2026-02-13-rlm-mcp-codex-companion-test-matrix.md tests/docs/test_readme_sections.py
git commit -m "docs: add mvp runbook and verification matrix"
```

## Verification Gate (Before declaring completion)

Run all tests:

```bash
PYTHONPATH=src pytest -v
```

Expected:
- Unit and integration suites all PASS.
- Guardrail stop reasons covered: `max_steps`, `timeout`, `budget_exceeded`.
- End-to-end flow demonstrates recursive/chunked processing pattern.

## Notes for Executor

- Apply DRY and YAGNI: do not add persistence/auth/multi-tenant features in this plan.
- Keep MCP tool payloads JSON-serializable and explicit.
- Prefer deterministic error codes over free-form error strings.
- If project is not initialized as git repo, initialize git before commit steps or defer commits until repo setup.
