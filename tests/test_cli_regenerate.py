from typer.testing import CliRunner

from claude_planner.cli import app
from claude_planner.models import InterviewStageResult, ProjectBrief

runner = CliRunner()


def _write_brief(output_dir):
    brief = ProjectBrief(
        project_name="Projekt",
        client_name="Klient",
        profile_ids=["web-fullstack"],
        intake_summary="brak",
        stages=[
            InterviewStageResult(role_id="product-manager", display_name="PM", qa=[], summary="ok")
        ],
    )
    meta_dir = output_dir / ".planner"
    meta_dir.mkdir(parents=True)
    (meta_dir / "brief.json").write_text(brief.model_dump_json(indent=2), encoding="utf-8")


def test_regenerate_uses_saved_brief_without_rerunning_interview(tmp_path, monkeypatch):
    monkeypatch.setattr("claude_planner.cli.ensure_claude_available", lambda: "/usr/bin/claude")

    output_dir = tmp_path / "project"
    output_dir.mkdir()
    _write_brief(output_dir)

    calls = {}

    def fake_generate_environment(brief, profiles, out_dir, model=None):
        calls["brief"] = brief
        calls["out_dir"] = out_dir
        return {"docs": ["vision.md"], "adr_count": 0, "agents": [], "commands": [], "skills": []}

    monkeypatch.setattr("claude_planner.cli.generate_environment", fake_generate_environment)

    result = runner.invoke(app, ["regenerate", str(output_dir)])

    assert result.exit_code == 0, result.output
    assert calls["brief"].project_name == "Projekt"
    assert calls["out_dir"] == output_dir


def test_regenerate_fails_clearly_when_no_brief_saved(tmp_path, monkeypatch):
    monkeypatch.setattr("claude_planner.cli.ensure_claude_available", lambda: "/usr/bin/claude")
    output_dir = tmp_path / "empty-project"
    output_dir.mkdir()

    result = runner.invoke(app, ["regenerate", str(output_dir)])

    assert result.exit_code == 1
    assert "brief.json" in result.output
