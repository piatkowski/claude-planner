import subprocess

import yaml
from rich.console import Console

from claude_planner.models import InterviewStageResult
from claude_planner.scaffold import ScaffoldError, run_init


def _stub_interview(monkeypatch):
    def fake_run(self, roles):
        return [
            InterviewStageResult(
                role_id=role.id, display_name=role.display_name, qa=[], summary=f"summary {role.id}"
            )
            for role in roles
        ]

    monkeypatch.setattr("claude_planner.scaffold.InterviewRunner.run", fake_run)
    monkeypatch.setattr("claude_planner.scaffold.summarize_intake", lambda *a, **k: "intake summary")
    monkeypatch.setattr(
        "claude_planner.scaffold.generate_environment",
        lambda brief, profiles, output_dir, model=None: {
            "docs": ["vision.md"], "adr_count": 0, "agents": [], "commands": [], "skills": [],
        },
    )


def test_run_init_creates_git_repo_and_metadata(tmp_path, monkeypatch):
    _stub_interview(monkeypatch)
    output_dir = tmp_path / "new-project"

    summary = run_init(
        project_name="Projekt",
        client_name="Klient",
        profile_ids=["web-fullstack"],
        output_dir=output_dir,
        intake_path=None,
        model=None,
        console=Console(),
    )

    assert summary["docs"] == ["vision.md"]
    assert (output_dir / ".git").is_dir()
    assert (output_dir / ".planner" / "project.yaml").exists()
    assert (output_dir / ".planner" / "interview-transcript.md").exists()

    metadata = yaml.safe_load((output_dir / ".planner" / "project.yaml").read_text())
    assert metadata["project_name"] == "Projekt"
    assert metadata["profile_ids"] == ["web-fullstack"]

    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=output_dir, capture_output=True, text=True, check=True
    )
    assert "initial claude-planner environment" in log.stdout


def test_run_init_rejects_nonempty_output_dir(tmp_path):
    output_dir = tmp_path / "exists"
    output_dir.mkdir()
    (output_dir / "file.txt").write_text("x")

    try:
        run_init(
            project_name="P",
            client_name="C",
            profile_ids=["web-fullstack"],
            output_dir=output_dir,
            intake_path=None,
            model=None,
            console=Console(),
        )
    except ScaffoldError as exc:
        assert "istnieje" in str(exc)
    else:
        raise AssertionError("expected ScaffoldError")


def test_run_init_rejects_empty_profile_list(tmp_path):
    try:
        run_init(
            project_name="P",
            client_name="C",
            profile_ids=[],
            output_dir=tmp_path / "proj",
            intake_path=None,
            model=None,
            console=Console(),
        )
    except ScaffoldError as exc:
        assert "profil" in str(exc)
    else:
        raise AssertionError("expected ScaffoldError")
