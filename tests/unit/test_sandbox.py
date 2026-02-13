from rlm_mcp.sandbox import SandboxExecutor


def test_exec_updates_variables_and_stdout():
    executor = SandboxExecutor()
    env = {"x": 1}
    out = executor.run("print(x)\ny = x + 1", env)
    assert "1" in out.stdout
    assert env["y"] == 2
