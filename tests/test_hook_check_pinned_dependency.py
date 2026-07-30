import json
import subprocess
import sys

import pytest

from claude_planner.templating import render


@pytest.fixture(scope="module")
def hook_script(tmp_path_factory):
    path = tmp_path_factory.mktemp("hooks") / "check-pinned-dependency.py"
    path.write_text(render("hook_check_pinned_dependency.py.j2"), encoding="utf-8")
    return path


def _run_hook(hook_script, command: str, tool_name: str = "Bash"):
    payload = json.dumps({"tool_name": tool_name, "tool_input": {"command": command}})
    return subprocess.run(
        [sys.executable, str(hook_script)],
        input=payload,
        capture_output=True,
        text=True,
    )


BLOCKED_COMMANDS = [
    "npm install left-pad@1.3.0",
    "pip install requests==2.31.0",
    "poetry add fastapi@0.110.0",
    "composer require symfony/console:6.4.0",
    "flutter pub add http:^1.2.0",
    "go get github.com/gin-gonic/gin@v1.9.1",
    "gem install rails -v 7.1.0",
    "cargo add serde@1.0.0",
]

ALLOWED_COMMANDS = [
    "npm install",
    "npm install left-pad",
    "pip install requests",
    "composer require symfony/console",
    "flutter pub get",
    "go get github.com/gin-gonic/gin@latest",
    "git status",
    "ls -la",
]


@pytest.mark.parametrize("command", BLOCKED_COMMANDS)
def test_blocks_pinned_version_installs(hook_script, command):
    result = _run_hook(hook_script, command)
    assert result.returncode == 2
    assert "NIE zgaduj" in result.stderr


@pytest.mark.parametrize("command", ALLOWED_COMMANDS)
def test_allows_unpinned_installs_and_other_commands(hook_script, command):
    result = _run_hook(hook_script, command)
    assert result.returncode == 0
    assert result.stderr == ""


def test_ignores_non_bash_tools(hook_script):
    result = _run_hook(hook_script, "pip install requests==2.31.0", tool_name="Read")
    assert result.returncode == 0


def test_handles_missing_command_gracefully(hook_script):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {}})
    result = subprocess.run(
        [sys.executable, str(hook_script)], input=payload, capture_output=True, text=True
    )
    assert result.returncode == 0


def test_handles_invalid_json_gracefully(hook_script):
    result = subprocess.run(
        [sys.executable, str(hook_script)], input="not json", capture_output=True, text=True
    )
    assert result.returncode == 0
