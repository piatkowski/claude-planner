import json

import pytest

from claude_planner.claude_client import (
    ClaudeCLIError,
    ClaudeNotFoundError,
    ClaudeSession,
    ensure_claude_available,
)


def test_ensure_claude_available_raises_when_missing(monkeypatch):
    monkeypatch.setattr("claude_planner.claude_client.shutil.which", lambda name: None)
    with pytest.raises(ClaudeNotFoundError):
        ensure_claude_available()


def test_first_turn_uses_session_id_and_system_prompt():
    session = ClaudeSession(system_prompt="be helpful", allowed_tools=["Read"])
    cmd = session._build_command("hello")
    assert "--session-id" in cmd
    assert session.session_id in cmd
    assert "--system-prompt" in cmd
    assert "be helpful" in cmd
    assert "--resume" not in cmd


def test_second_turn_uses_resume_not_session_id():
    session = ClaudeSession()
    session._turns = 1
    cmd = session._build_command("hello again")
    assert "--resume" in cmd
    assert session.session_id in cmd
    assert "--session-id" not in cmd


def test_json_schema_flag_included_when_set():
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    session = ClaudeSession(json_schema=schema)
    cmd = session._build_command("hi")
    assert "--json-schema" in cmd
    idx = cmd.index("--json-schema")
    assert json.loads(cmd[idx + 1]) == schema


def test_no_allowed_tools_disables_all_tools():
    session = ClaudeSession(allowed_tools=[])
    cmd = session._build_command("hi")
    idx = cmd.index("--tools")
    assert cmd[idx + 1] == ""
    assert "--allowedTools" not in cmd


def test_allowed_tools_restricts_tool_set_and_auto_approves_them():
    session = ClaudeSession(allowed_tools=["Read", "Glob"])
    cmd = session._build_command("hi")

    tools_idx = cmd.index("--tools")
    assert cmd[tools_idx + 1] == "Read,Glob"

    allowed_idx = cmd.index("--allowedTools")
    assert cmd[allowed_idx + 1] == "Read Glob"


def test_parse_output_success():
    stdout = json.dumps({"result": "hello world", "session_id": "abc", "is_error": False})
    result = ClaudeSession._parse_output(stdout, "")
    assert result.text == "hello world"
    assert result.session_id == "abc"
    assert result.is_error is False


def test_parse_output_raises_on_error_flag():
    stdout = json.dumps({"result": "boom", "is_error": True})
    with pytest.raises(ClaudeCLIError):
        ClaudeSession._parse_output(stdout, "")


def test_parse_output_raises_on_invalid_json():
    with pytest.raises(ClaudeCLIError):
        ClaudeSession._parse_output("not json", "some stderr")


def test_parse_output_raises_on_empty_stdout():
    with pytest.raises(ClaudeCLIError):
        ClaudeSession._parse_output("   ", "some stderr")
