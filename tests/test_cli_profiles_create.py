import json
from pathlib import Path

from typer.testing import CliRunner

from claude_planner.cli import _resolve_profiles_dir, app
from claude_planner.models import StackProfile

runner = CliRunner()

FAKE_PROFILE = StackProfile(
    id="ruby-on-rails",
    name="Ruby on Rails",
    description="Monolit webowy w Ruby on Rails.",
    languages=["Ruby"],
    frameworks=["Rails"],
    setup_commands=["bundle install"],
)


def test_profiles_create_writes_yaml_file(tmp_path, monkeypatch):
    monkeypatch.setattr("claude_planner.cli.ensure_claude_available", lambda: "/usr/bin/claude")
    monkeypatch.setattr(
        "claude_planner.cli.generate_profile", lambda *a, **k: FAKE_PROFILE
    )

    result = runner.invoke(
        app,
        [
            "profiles",
            "create",
            "Ruby on Rails + Sidekiq",
            "--id",
            "ruby-on-rails",
            "--profiles-dir",
            str(tmp_path),
            "--model",
            "sonnet",
        ],
    )

    assert result.exit_code == 0, result.output
    written = tmp_path / "ruby-on-rails.yaml"
    assert written.exists()
    assert "Ruby on Rails" in written.read_text(encoding="utf-8")


def test_profiles_list_includes_custom_profile(tmp_path, monkeypatch):
    (tmp_path / "custom-one.yaml").write_text(
        json.dumps(
            {
                "id": "custom-one",
                "name": "Custom One",
                "description": "opis",
            }
        ),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["profiles", "list", "--profiles-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "custom-one" in result.output


def test_resolve_profiles_dir_expands_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    resolved = _resolve_profiles_dir(Path("~/.claude-planner/profiles"))

    assert resolved == tmp_path / ".claude-planner" / "profiles"


def test_profiles_list_includes_custom_profile_from_config_with_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    profiles_dir = tmp_path / ".claude-planner" / "profiles"
    profiles_dir.mkdir(parents=True)
    (profiles_dir / "php.yaml").write_text(
        json.dumps({"id": "php", "name": "PHP", "description": "opis"}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app, ["profiles", "list", "--profiles-dir", "~/.claude-planner/profiles"]
    )

    assert result.exit_code == 0, result.output
    assert "php" in result.output
