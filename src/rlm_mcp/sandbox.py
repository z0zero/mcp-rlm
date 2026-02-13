from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from textwrap import dedent
from typing import Any

_WORKER_CODE = dedent(
    r"""
    import builtins
    import io
    import json
    import resource
    import sys
    from contextlib import redirect_stderr, redirect_stdout

    def _encode(value):
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, list):
            return [_encode(v) for v in value]
        if isinstance(value, tuple):
            return {"__tuple__": [_encode(v) for v in value]}
        if isinstance(value, set):
            return {"__set__": [_encode(v) for v in value]}
        if isinstance(value, dict):
            return {"__dict__": [[str(k), _encode(v)] for k, v in value.items()]}
        return {"__repr__": repr(value)}

    def _decode(value):
        if isinstance(value, list):
            return [_decode(v) for v in value]
        if isinstance(value, dict):
            if "__tuple__" in value:
                return tuple(_decode(v) for v in value["__tuple__"])
            if "__set__" in value:
                return set(_decode(v) for v in value["__set__"])
            if "__dict__" in value:
                return {k: _decode(v) for k, v in value["__dict__"]}
            if "__repr__" in value:
                return value["__repr__"]
        return value

    def _apply_limits(payload):
        cpu_seconds = max(1, int(payload.get("cpu_seconds", 2)))
        memory_limit_bytes = int(payload.get("memory_limit_bytes", 268435456))
        max_open_files = max(16, int(payload.get("max_open_files", 32)))
        max_file_size_bytes = int(payload.get("max_file_size_bytes", 0))

        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        if hasattr(resource, "RLIMIT_AS"):
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
        if hasattr(resource, "RLIMIT_NOFILE"):
            resource.setrlimit(resource.RLIMIT_NOFILE, (max_open_files, max_open_files))
        if hasattr(resource, "RLIMIT_FSIZE"):
            resource.setrlimit(resource.RLIMIT_FSIZE, (max_file_size_bytes, max_file_size_bytes))

    def _build_safe_builtins(allowed_import_roots):
        safe = {
            "abs": builtins.abs,
            "all": builtins.all,
            "any": builtins.any,
            "bool": builtins.bool,
            "dict": builtins.dict,
            "enumerate": builtins.enumerate,
            "Exception": builtins.Exception,
            "float": builtins.float,
            "int": builtins.int,
            "isinstance": builtins.isinstance,
            "len": builtins.len,
            "list": builtins.list,
            "max": builtins.max,
            "min": builtins.min,
            "print": builtins.print,
            "range": builtins.range,
            "set": builtins.set,
            "sorted": builtins.sorted,
            "str": builtins.str,
            "sum": builtins.sum,
            "tuple": builtins.tuple,
            "zip": builtins.zip,
        }

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root = name.split(".")[0]
            if root not in allowed_import_roots:
                raise ImportError(f"import '{name}' is blocked by sandbox policy")
            return builtins.__import__(name, globals, locals, fromlist, level)

        safe["__import__"] = guarded_import
        return safe

    def _trim_output(text, limit):
        if len(text) <= limit:
            return text
        return text[:limit] + "\n...[truncated by sandbox output limit]...\n"

    def main():
        payload = json.loads(sys.stdin.read())
        _apply_limits(payload)

        allowed_import_roots = set(payload.get("allowed_import_roots", []))
        safe_builtins = _build_safe_builtins(allowed_import_roots)
        scope = {"__builtins__": safe_builtins}
        for key, value in payload.get("env", {}).items():
            scope[key] = _decode(value)

        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        error = None
        code = payload.get("code", "")
        output_limit = int(payload.get("max_output_chars", 200000))

        try:
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                exec(code, scope, scope)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            if stderr_buffer.getvalue() == "":
                stderr_buffer.write(error + "\n")

        out_env = {}
        for key, value in scope.items():
            if not key.startswith("__"):
                out_env[key] = _encode(value)

        result = {
            "stdout": _trim_output(stdout_buffer.getvalue(), output_limit),
            "stderr": _trim_output(stderr_buffer.getvalue(), output_limit),
            "error": error,
            "env": out_env,
        }
        sys.stdout.write(json.dumps(result))

    if __name__ == "__main__":
        main()
    """
)


@dataclass(slots=True)
class SandboxResult:
    stdout: str
    stderr: str
    error: str | None = None


class SandboxExecutor:
    def __init__(
        self,
        *,
        sandbox_mode: str | None = None,
        memory_limit_mb: int = 256,
        max_open_files: int = 32,
        max_output_chars: int = 200_000,
        allowed_import_roots: tuple[str, ...] | None = None,
        fallback_to_subprocess: bool = True,
        container_runtime: str | None = None,
        container_image: str | None = None,
        container_pids_limit: int = 128,
        container_tmpfs_size_mb: int = 32,
    ) -> None:
        mode = (sandbox_mode or os.getenv("RLM_SANDBOX_MODE", "subprocess")).strip().lower()
        if mode not in {"subprocess", "container"}:
            raise ValueError("sandbox_mode must be 'subprocess' or 'container'")

        self.sandbox_mode = mode
        self.memory_limit_mb = memory_limit_mb
        self.max_open_files = max_open_files
        self.max_output_chars = max_output_chars
        self.fallback_to_subprocess = fallback_to_subprocess
        self.container_runtime = (container_runtime or os.getenv("RLM_SANDBOX_CONTAINER_RUNTIME", "docker")).strip()
        self.container_image = (container_image or os.getenv("RLM_SANDBOX_CONTAINER_IMAGE", "python:3.12-alpine")).strip()
        self.container_pids_limit = max(32, container_pids_limit)
        self.container_tmpfs_size_mb = max(8, container_tmpfs_size_mb)
        self.allowed_import_roots = allowed_import_roots or (
            "math",
            "statistics",
            "re",
            "json",
            "datetime",
            "itertools",
            "functools",
            "collections",
        )

    def run(self, code: str, env: dict[str, Any], timeout_ms: int = 2000) -> SandboxResult:
        payload = {
            "code": code,
            "env": {key: self._encode_value(value) for key, value in env.items()},
            "cpu_seconds": max(1, int((timeout_ms / 1000.0) + 1)),
            "memory_limit_bytes": self.memory_limit_mb * 1024 * 1024,
            "max_open_files": self.max_open_files,
            "max_file_size_bytes": 0,
            "max_output_chars": self.max_output_chars,
            "allowed_import_roots": list(self.allowed_import_roots),
        }

        if self.sandbox_mode == "container":
            container_cmd = self._build_container_command()
            result, updates = self._execute_worker(container_cmd, payload, timeout_ms=timeout_ms, timeout_label="container")
            if result.error and self.fallback_to_subprocess and self._is_runtime_missing_error(result.error):
                result, updates = self._execute_worker(
                    self._build_subprocess_command(),
                    payload,
                    timeout_ms=timeout_ms,
                    timeout_label="subprocess",
                )
        else:
            result, updates = self._execute_worker(
                self._build_subprocess_command(),
                payload,
                timeout_ms=timeout_ms,
                timeout_label="subprocess",
            )

        self._apply_env_updates(env, updates)
        return result

    def _build_subprocess_command(self) -> list[str]:
        return [sys.executable, "-I", "-S", "-c", _WORKER_CODE]

    def _build_container_command(self) -> list[str]:
        return [
            self.container_runtime,
            "run",
            "--rm",
            "-i",
            "--network",
            "none",
            "--read-only",
            "--pids-limit",
            str(self.container_pids_limit),
            "--memory",
            f"{self.memory_limit_mb}m",
            "--cpus",
            "1.0",
            "--security-opt",
            "no-new-privileges",
            "--cap-drop",
            "ALL",
            "--tmpfs",
            f"/tmp:rw,noexec,nosuid,size={self.container_tmpfs_size_mb}m",
            "--user",
            "65532:65532",
            self.container_image,
            "python",
            "-I",
            "-S",
            "-c",
            _WORKER_CODE,
        ]

    def _execute_worker(
        self,
        command: list[str],
        payload: dict[str, Any],
        *,
        timeout_ms: int,
        timeout_label: str,
    ) -> tuple[SandboxResult, dict[str, Any]]:
        try:
            proc = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = proc.communicate(
                input=json.dumps(payload),
                timeout=max(1.0, timeout_ms / 1000.0),
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            error = f"TimeoutError: sandbox {timeout_label} timed out"
            return SandboxResult(stdout="", stderr=error + "\n", error=error), {}
        except Exception as exc:  # pragma: no cover
            error = f"SandboxProcessError: {type(exc).__name__}: {exc}"
            return SandboxResult(stdout="", stderr=error + "\n", error=error), {}

        if proc.returncode != 0:
            if proc.returncode < 0 and abs(proc.returncode) in {9, 24, 25}:
                error = f"TimeoutError: sandbox {timeout_label} exceeded execution limits"
                return SandboxResult(stdout="", stderr=error + "\n", error=error), {}
            error = f"SandboxProcessError: {timeout_label} exited with code {proc.returncode}"
            detail = (stderr or "").strip()
            if detail:
                error = f"{error}: {detail}"
            return SandboxResult(stdout="", stderr=error + "\n", error=error), {}

        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            error = "SandboxProcessError: invalid worker response"
            detail = (stderr or "").strip()
            if detail:
                error = f"{error}: {detail}"
            return SandboxResult(stdout="", stderr=error + "\n", error=error), {}

        updates = result.get("env", {})
        if not isinstance(updates, dict):
            updates = {}

        return (
            SandboxResult(
                stdout=result.get("stdout", ""),
                stderr=result.get("stderr", ""),
                error=result.get("error"),
            ),
            updates,
        )

    def _apply_env_updates(self, env: dict[str, Any], updates: dict[str, Any]) -> None:
        for key, value in updates.items():
            env[key] = self._decode_value(value)

    @staticmethod
    def _is_runtime_missing_error(error: str) -> bool:
        return "FileNotFoundError" in error or "No such file or directory" in error

    @staticmethod
    def _encode_value(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, list):
            return [SandboxExecutor._encode_value(v) for v in value]
        if isinstance(value, tuple):
            return {"__tuple__": [SandboxExecutor._encode_value(v) for v in value]}
        if isinstance(value, set):
            return {"__set__": [SandboxExecutor._encode_value(v) for v in value]}
        if isinstance(value, dict):
            return {"__dict__": [[str(k), SandboxExecutor._encode_value(v)] for k, v in value.items()]}
        return {"__repr__": repr(value)}

    @staticmethod
    def _decode_value(value: Any) -> Any:
        if isinstance(value, list):
            return [SandboxExecutor._decode_value(v) for v in value]
        if isinstance(value, dict):
            if "__tuple__" in value:
                return tuple(SandboxExecutor._decode_value(v) for v in value["__tuple__"])
            if "__set__" in value:
                return set(SandboxExecutor._decode_value(v) for v in value["__set__"])
            if "__dict__" in value:
                return {k: SandboxExecutor._decode_value(v) for k, v in value["__dict__"]}
            if "__repr__" in value:
                return value["__repr__"]
        return value
