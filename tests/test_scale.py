from claude_planner.models import ProjectScale
from claude_planner.scale import assess_project_scale, qa_scale_instruction


def test_assess_project_scale_parses_valid_response(monkeypatch):
    monkeypatch.setattr(
        "claude_planner.scale.one_shot",
        lambda *a, **k: '{"scale": "Micro", "justification": "jeden deweloper, PHP"}',
    )
    scale, justification = assess_project_scale("kontekst projektu")
    assert scale == ProjectScale.MICRO
    assert justification == "jeden deweloper, PHP"


def test_assess_project_scale_falls_back_to_small_on_error(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("claude CLI not available")

    monkeypatch.setattr("claude_planner.scale.one_shot", _boom)
    scale, justification = assess_project_scale("kontekst projektu")
    assert scale == ProjectScale.SMALL
    assert justification


def test_qa_scale_instruction_none_scale_returns_empty_string():
    assert qa_scale_instruction(None) == ""


def test_qa_scale_instruction_micro_forbids_enterprise_topics():
    instruction = qa_scale_instruction(ProjectScale.MICRO)
    assert "Micro" in instruction
    assert "CI/CD" in instruction
    assert "Zignoruj" in instruction


def test_qa_scale_instruction_enterprise_requires_full_platform_topics():
    instruction = qa_scale_instruction(ProjectScale.ENTERPRISE)
    assert "Enterprise" in instruction
    assert "WCAG" in instruction
