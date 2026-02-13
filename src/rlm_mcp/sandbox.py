from __future__ import annotations

import signal
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from typing import Any


@dataclass(slots=True)
class SandboxResult:
    stdout: str
    stderr: str
    error: str | None = None


class SandboxExecutor:
    _SAFE_BUILTINS = {
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "print": print,
        "range": range,
        "set": set,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }

    def run(self, code: str, env: dict[str, Any], timeout_ms: int = 2000) -> SandboxResult:
        stdout_buffer = StringIO()
        stderr_buffer = StringIO()
        error: str | None = None

        scope: dict[str, Any] = {"__builtins__": self._SAFE_BUILTINS}
        scope.update(env)

        def _on_timeout(_signum: int, _frame: Any) -> None:
            raise TimeoutError("sandbox execution timed out")

        old_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, _on_timeout)
        signal.setitimer(signal.ITIMER_REAL, timeout_ms / 1000.0)

        try:
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                exec(code, scope, scope)
        except Exception as exc:  # pragma: no cover - behavior asserted via stderr/error
            error = f"{type(exc).__name__}: {exc}"
            if stderr_buffer.getvalue() == "":
                stderr_buffer.write(error + "\n")
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)

            for key, value in scope.items():
                if not key.startswith("__"):
                    env[key] = value

        return SandboxResult(stdout=stdout_buffer.getvalue(), stderr=stderr_buffer.getvalue(), error=error)
