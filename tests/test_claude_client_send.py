import json
import subprocess
from types import SimpleNamespace

from claude_planner.claude_client import ClaudeSession


def test_send_returns_parsed_result(monkeypatch):
    monkeypatch.setattr("claude_planner.claude_client.shutil.which", lambda name: "/usr/bin/claude")

    captured = {}

    def fake_run(cmd, capture_output, text, timeout, cwd):
        captured["cmd"] = cmd
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"result": "the answer", "session_id": "sid-1", "is_error": False}),
            stderr="",
        )

    monkeypatch.setattr("claude_planner.claude_client.subprocess.run", fake_run)

    session = ClaudeSession()
    result = session.send("question?")

    assert result.text == "the answer"
    assert "-p" in captured["cmd"]
    assert "question?" in captured["cmd"]
    assert session._turns == 1

    # second call should resume the same session
    monkeypatch.setattr(
        "claude_planner.claude_client.subprocess.run",
        lambda *a, **k: SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"result": "follow up", "session_id": "sid-1", "is_error": False}),
            stderr="",
        ),
    )
    result2 = session.send("another question")
    assert result2.text == "follow up"
    assert session._turns == 2


def test_send_raises_on_nonzero_returncode(monkeypatch):
    monkeypatch.setattr("claude_planner.claude_client.shutil.which", lambda name: "/usr/bin/claude")
    monkeypatch.setattr(
        "claude_planner.claude_client.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )
    session = ClaudeSession()
    try:
        session.send("hi")
    except Exception as exc:
        assert "boom" in str(exc)
    else:
        raise AssertionError("expected ClaudeCLIError")
