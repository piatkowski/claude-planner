import json

from claude_planner.generator import generate_environment
from claude_planner.models import InterviewStageResult, ProjectBrief
from claude_planner.profiles import get_profile


def _fake_one_shot(prompt, *, allowed_tools=None, add_dirs=None, model=None, json_schema=None):
    if json_schema is not None:
        return json.dumps(
            {
                "decisions": [
                    {
                        "title": "Wybór bazy danych",
                        "context": "Potrzebujemy relacyjnej bazy.",
                        "decision": "Używamy PostgreSQL.",
                        "consequences": "Musimy zarządzać migracjami.",
                    }
                ]
            }
        )
    return "# Wygenerowany dokument\n\nTreść testowa.\n"


def _brief():
    return ProjectBrief(
        project_name="Projekt Testowy",
        client_name="Klient Testowy",
        profile_ids=["web-fullstack"],
        intake_summary="(brak materiałów)",
        stages=[
            InterviewStageResult(
                role_id="product-manager",
                display_name="Product Manager / Business Analyst",
                qa=[],
                summary="Klient chce sklep internetowy.",
            )
        ],
    )


def test_generate_environment_writes_full_structure(tmp_path, monkeypatch):
    monkeypatch.setattr("claude_planner.generator.one_shot", _fake_one_shot)

    profiles = [get_profile("web-fullstack")]
    brief = _brief()
    output_dir = tmp_path / "project"
    output_dir.mkdir()

    summary = generate_environment(brief, profiles, output_dir)

    for doc in [
        "vision.md", "prd.md", "roadmap.md", "coding-standards.md",
        "definition-of-done.md", "test-strategy.md",
    ]:
        assert (output_dir / "docs" / doc).exists()

    assert (output_dir / "docs" / "adr" / "template.md").exists()
    assert (output_dir / "docs" / "adr" / "README.md").exists()
    assert (output_dir / "docs" / "adr" / "0001-wybor-bazy-danych.md").exists()
    assert summary["adr_count"] == 1

    assert (output_dir / "CLAUDE.md").exists()
    assert (output_dir / "state.md").exists()
    assert (output_dir / "README.md").exists()

    for role_id in ["product-manager", "architect", "backend-frontend-dev", "qa-devops-ux"]:
        assert (output_dir / ".claude" / "agents" / f"{role_id}.md").exists()
    assert (output_dir / ".claude" / "agents" / "api-contract-guardian.md").exists()

    for command in [
        "new-adr", "update-roadmap", "update-state", "log-decision",
        "daily-standup", "sprint-review",
    ]:
        assert (output_dir / ".claude" / "commands" / f"{command}.md").exists()

    assert (output_dir / ".claude" / "skills" / "frontend-component-conventions" / "SKILL.md").exists()
    assert (output_dir / ".claude" / "settings.json").exists()

    assert (output_dir / ".claude" / "commands" / "setup-dev-environment.md").exists()
    setup_cmd = (output_dir / ".claude" / "commands" / "setup-dev-environment.md").read_text(
        encoding="utf-8"
    )
    assert "npm install" in setup_cmd
    assert "Web Fullstack" in setup_cmd

    assert (output_dir / ".claude" / "hooks" / "check-pinned-dependency.py").exists()
    settings = json.loads((output_dir / ".claude" / "settings.json").read_text(encoding="utf-8"))
    pre_tool_use = settings["hooks"]["PreToolUse"]
    assert pre_tool_use[0]["matcher"] == "Bash"
    assert "check-pinned-dependency.py" in pre_tool_use[0]["hooks"][0]["command"]
    # Hooki muszą używać $CLAUDE_PROJECT_DIR — ścieżka względna zawodzi, gdy sesja
    # Claude Code jest uruchomiona z innego cwd niż root projektu (np. z podkatalogu).
    assert "$CLAUDE_PROJECT_DIR" in pre_tool_use[0]["hooks"][0]["command"]
    session_start = settings["hooks"]["SessionStart"]
    assert "$CLAUDE_PROJECT_DIR" in session_start[0]["hooks"][0]["command"]

    assert "setup-dev-environment" in summary["commands"]

    assert (output_dir / "WORKFLOW.md").exists()
    workflow = (output_dir / "WORKFLOW.md").read_text(encoding="utf-8")
    assert "product-manager" in workflow
    assert "/update-state" in workflow
    assert "frontend-component-conventions" in workflow
    assert "/setup-dev-environment" in workflow


def test_state_md_contains_profile_names_and_is_overwrite_style(tmp_path, monkeypatch):
    monkeypatch.setattr("claude_planner.generator.one_shot", _fake_one_shot)
    profiles = [get_profile("web-fullstack")]
    output_dir = tmp_path / "project"
    output_dir.mkdir()

    generate_environment(_brief(), profiles, output_dir)

    content = (output_dir / "state.md").read_text(encoding="utf-8")
    assert "Web Fullstack" in content
    assert "NADPISYWANY" in content


def test_base_agent_body_includes_stage_summary(tmp_path, monkeypatch):
    monkeypatch.setattr("claude_planner.generator.one_shot", _fake_one_shot)
    profiles = [get_profile("web-fullstack")]
    output_dir = tmp_path / "project"
    output_dir.mkdir()

    generate_environment(_brief(), profiles, output_dir)

    pm_agent = (output_dir / ".claude" / "agents" / "product-manager.md").read_text(encoding="utf-8")
    assert "Klient chce sklep internetowy." in pm_agent
