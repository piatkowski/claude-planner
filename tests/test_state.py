from claude_planner.models import ProjectState
from claude_planner.state import (
    apply_new_facts,
    extract_new_facts,
    render_state_snapshot,
)


def test_render_state_snapshot_empty():
    assert "brak ustalonych" in render_state_snapshot(ProjectState())


def test_render_state_snapshot_lists_facts():
    state = ProjectState(facts={"hosting": "AWS", "budzet": "50000 PLN"})
    snapshot = render_state_snapshot(state)
    assert "hosting: AWS" in snapshot
    assert "budzet: 50000 PLN" in snapshot


def test_apply_new_facts_merges_and_tracks_source():
    state = ProjectState()
    apply_new_facts(state, "architect", {"hosting": "AWS"})
    assert state.facts == {"hosting": "AWS"}
    assert state.fact_sources == {"hosting": "architect"}

    apply_new_facts(state, "qa-devops-ux", {"hosting": "GCP", "monitoring": "Sentry"})
    assert state.facts == {"hosting": "GCP", "monitoring": "Sentry"}
    assert state.fact_sources["hosting"] == "qa-devops-ux"


def test_extract_new_facts_returns_empty_dict_when_claude_unavailable(monkeypatch):
    """Ekstrakcja faktów to poboczne wywołanie LLM — jeśli `claude` nie jest dostępny
    albo padnie, wywiad nie może się z tego powodu wysypać."""

    def _boom(*args, **kwargs):
        raise RuntimeError("claude CLI not available in test sandbox")

    monkeypatch.setattr("claude_planner.state.one_shot", _boom)
    facts = extract_new_facts(
        role_display_name="Architekt",
        question="Gdzie hostujemy?",
        answer="AWS",
        state=ProjectState(),
    )
    assert facts == {}


def test_extract_new_facts_filters_non_string_and_empty_values(monkeypatch):
    monkeypatch.setattr(
        "claude_planner.state.one_shot",
        lambda *a, **k: (
            '{"facts": {"budzet": "50000 PLN", "liczba_userow": 300, "puste": ""}}'
        ),
    )
    facts = extract_new_facts(
        role_display_name="PM",
        question="Jaki budżet?",
        answer="50000 PLN, ok. 300 userów",
        state=ProjectState(),
    )
    assert facts == {"budzet": "50000 PLN"}


def test_extract_new_facts_skips_facts_already_known(monkeypatch):
    captured_prompt = {}

    def fake_one_shot(prompt, **kwargs):
        captured_prompt["value"] = prompt
        return '{"facts": {}}'

    monkeypatch.setattr("claude_planner.state.one_shot", fake_one_shot)
    state = ProjectState(facts={"hosting": "AWS"})
    facts = extract_new_facts(
        role_display_name="Architekt",
        question="Jaki hosting?",
        answer="AWS, jak już mówiłem",
        state=state,
    )
    assert facts == {}
    assert "hosting: AWS" in captured_prompt["value"]
