from rlm_mcp.sandbox import SandboxExecutor


def test_exec_updates_variables_and_stdout():
    executor = SandboxExecutor()
    env = {"x": 1}
    out = executor.run("print(x)\ny = x + 1", env)
    assert "1" in out.stdout
    assert env["y"] == 2


def test_blocks_non_whitelisted_imports():
    executor = SandboxExecutor()
    env = {}
    out = executor.run("import os\nx = 1", env)
    assert out.error is not None
    assert "blocked by sandbox policy" in out.stderr
    assert "x" not in env


def test_times_out_infinite_loop():
    executor = SandboxExecutor()
    env = {}
    out = executor.run("while True:\n    pass", env, timeout_ms=300)
    assert out.error is not None
    assert "TimeoutError" in out.error


def test_truncates_large_stdout():
    executor = SandboxExecutor(max_output_chars=64)
    env = {}
    out = executor.run("print('a' * 1000)", env)
    assert "...[truncated by sandbox output limit]..." in out.stdout


def test_container_command_contains_hardening_flags():
    executor = SandboxExecutor(
        sandbox_mode="container",
        container_runtime="docker",
        container_image="python:3.12-alpine",
    )
    cmd = executor._build_container_command()
    assert cmd[0] == "docker"
    assert "--network" in cmd and "none" in cmd
    assert "--read-only" in cmd
    assert "--cap-drop" in cmd and "ALL" in cmd
    assert "--security-opt" in cmd and "no-new-privileges" in cmd
    assert "--tmpfs" in cmd


def test_container_mode_falls_back_to_subprocess_when_runtime_missing():
    executor = SandboxExecutor(
        sandbox_mode="container",
        container_runtime="definitely-not-a-runtime",
        fallback_to_subprocess=True,
    )
    env = {"x": 2}
    out = executor.run("y = x + 3", env)
    assert out.error is None
    assert env["y"] == 5


def test_container_mode_without_fallback_returns_runtime_error():
    executor = SandboxExecutor(
        sandbox_mode="container",
        container_runtime="definitely-not-a-runtime",
        fallback_to_subprocess=False,
    )
    env = {}
    out = executor.run("x = 1", env)
    assert out.error is not None
    assert "FileNotFoundError" in out.error
