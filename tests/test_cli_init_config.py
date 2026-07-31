import json
from pathlib import Path

from typer.testing import CliRunner

from claude_planner.cli import app

runner = CliRunner()

FAKE_SUMMARY = {"docs": ["vision.md"], "adr_count": 0, "agents": [], "commands": [], "skills": []}


def _stub_run_init(monkeypatch):
    calls = {}

    def fake_run_init(**kwargs):
        calls.update(kwargs)
        return FAKE_SUMMARY

    monkeypatch.setattr("claude_planner.cli.ensure_claude_available", lambda: "/usr/bin/claude")
    monkeypatch.setattr("claude_planner.cli.run_init", fake_run_init)
    return calls


def test_init_uses_claude_planner_json_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = _stub_run_init(monkeypatch)

    (tmp_path / "claude-planner.json").write_text(
        json.dumps(
            {
                "name": "Sklep XYZ",
                "client": "Acme",
                "output": "./sklep-xyz",
                "profiles": ["web-fullstack"],
                "model": "opus",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["init"], input="\ny\n")

    assert result.exit_code == 0, result.output
    assert calls["project_name"] == "Sklep XYZ"
    assert calls["client_name"] == "Acme"
    assert calls["output_dir"] == Path("sklep-xyz")
    assert calls["profile_ids"] == ["web-fullstack"]
    assert calls["model"] == "opus"


def test_init_cli_flags_override_config_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = _stub_run_init(monkeypatch)

    (tmp_path / "claude-planner.json").write_text(
        json.dumps({"name": "Sklep XYZ", "client": "Acme", "model": "sonnet"}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["init", "--client", "Inny Klient", "--output", "./out", "--profile", "generic", "--model", "opus"],
        input="\ny\n",
    )

    assert result.exit_code == 0, result.output
    assert calls["project_name"] == "Sklep XYZ"
    assert calls["client_name"] == "Inny Klient"
    assert calls["output_dir"] == Path("out")
    assert calls["profile_ids"] == ["generic"]
    assert calls["model"] == "opus"


def test_init_missing_explicit_config_file_errors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _stub_run_init(monkeypatch)

    result = runner.invoke(app, ["init", "--config", str(tmp_path / "missing.json")])

    assert result.exit_code == 1
    assert "missing.json" in result.output


def test_init_invalid_config_field_errors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _stub_run_init(monkeypatch)

    (tmp_path / "claude-planner.json").write_text(
        json.dumps({"name": "Sklep XYZ", "unknown_field": "boom"}), encoding="utf-8"
    )

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 1
    assert "Nieprawidłowa konfiguracja" in result.output
