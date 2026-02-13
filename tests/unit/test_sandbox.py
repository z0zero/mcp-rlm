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
