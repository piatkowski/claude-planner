import json

import pytest

from claude_planner.claude_client import ClaudeCLIError, ClaudeTurnResult
from claude_planner.interview import InterviewRunner
from claude_planner.models import InterviewRole, ProjectScale


def _turn(action, **kwargs):
    payload = {"action": action, **kwargs}
    return ClaudeTurnResult(text=json.dumps(payload), session_id="sid")


class FakeSession:
    """Replays a scripted sequence of turns instead of calling `claude`."""

    def __init__(self, script, **kwargs):
        self._script = list(script)
        self.kwargs = kwargs

    def send(self, prompt):
        return self._script.pop(0)


ROLE = InterviewRole(
    id="test-role",
    display_name="Test Role",
    persona="jesteś testerem",
    topics=["temat A", "temat B"],
    goal="zebrać dane testowe",
)


@pytest.fixture(autouse=True)
def _no_side_llm_calls(monkeypatch):
    """Moduły 1 i 3 robią poboczne wywołania LLM (ekstrakcja faktów, ocena skali).
    Domyślnie w testach neutralizujemy je (żadnych nowych faktów, brak oceny skali)
    tak, żeby testy skupione na logice orkiestracji nie zależały od `claude` CLI;
    testy, które chcą sprawdzić te zachowania wprost, nadpisują je lokalnie."""
    monkeypatch.setattr("claude_planner.interview.extract_new_facts", lambda **kw: {})
    monkeypatch.setattr(
        "claude_planner.interview.assess_project_scale", lambda *a, **k: (None, "")
    )


def test_stage_ends_when_claude_signals_done(monkeypatch):
    script = [
        _turn("question", question="Pierwsze pytanie?"),
        _turn("done", summary="Podsumowanie etapu."),
    ]
    monkeypatch.setattr(
        "claude_planner.interview.ClaudeSession", lambda **kw: FakeSession(script)
    )
    monkeypatch.setattr("claude_planner.interview.Prompt.ask", lambda *a, **k: "moja odpowiedź")

    runner = InterviewRunner(
        project_name="Projekt X", client_name="Klient Y", profiles=[], intake_path=None
    )
    stages = runner.run([ROLE])

    assert len(stages) == 1
    stage = stages[0]
    assert stage.role_id == "test-role"
    assert stage.summary == "Podsumowanie etapu."
    assert len(stage.qa) == 1
    assert stage.qa[0].answer == "moja odpowiedź"


def test_user_can_force_end_stage(monkeypatch):
    script = [
        _turn("question", question="Pierwsze pytanie?"),
        _turn("done", summary="Zakończono na życzenie użytkownika."),
    ]
    monkeypatch.setattr(
        "claude_planner.interview.ClaudeSession", lambda **kw: FakeSession(script)
    )
    monkeypatch.setattr("claude_planner.interview.Prompt.ask", lambda *a, **k: "koniec")

    runner = InterviewRunner(
        project_name="Projekt X", client_name="Klient Y", profiles=[], intake_path=None
    )
    stages = runner.run([ROLE])

    assert stages[0].summary == "Zakończono na życzenie użytkownika."
    assert stages[0].qa == []


def test_stage_summaries_carry_over_as_context(monkeypatch):
    calls = []

    def make_session(**kwargs):
        calls.append(kwargs["system_prompt"])
        return FakeSession([_turn("done", summary=f"summary for {len(calls)}")])

    monkeypatch.setattr("claude_planner.interview.ClaudeSession", make_session)

    role_2 = InterviewRole(
        id="role-2", display_name="Role 2", persona="p", topics=["t"], goal="g"
    )
    runner = InterviewRunner(
        project_name="P", client_name="C", profiles=[], intake_path=None
    )
    runner.run([ROLE, role_2])

    assert "summary for 1" in calls[1]


def test_fallback_when_claude_returns_non_json(monkeypatch):
    class NonJsonSession:
        def __init__(self, **kw):
            self._sent = False

        def send(self, prompt):
            if not self._sent:
                self._sent = True
                return ClaudeTurnResult(text="Jakie jest Twoje imię?", session_id="sid")
            return _turn("done", summary="ok")

    monkeypatch.setattr("claude_planner.interview.ClaudeSession", lambda **kw: NonJsonSession())
    monkeypatch.setattr("claude_planner.interview.Prompt.ask", lambda *a, **k: "Jan")

    runner = InterviewRunner(
        project_name="P", client_name="C", profiles=[], intake_path=None
    )
    stages = runner.run([ROLE])
    assert stages[0].qa[0].question == "Jakie jest Twoje imię?"


def test_state_facts_from_one_stage_are_injected_into_next_stage_prompt(monkeypatch):
    """Moduł 1 (Blackboard): fakt ustalony w etapie 1 musi trafić do system promptu
    etapu 2 (i pozostać nieobecny w system prompcie etapu 1, zanim jeszcze istniał)."""
    calls = []

    def make_session(**kwargs):
        calls.append(kwargs["system_prompt"])
        if len(calls) == 1:
            return FakeSession(
                [_turn("question", question="Gdzie hostujemy?"), _turn("done", summary="s1")]
            )
        return FakeSession([_turn("done", summary="s2")])

    monkeypatch.setattr("claude_planner.interview.ClaudeSession", make_session)
    monkeypatch.setattr("claude_planner.interview.Prompt.ask", lambda *a, **k: "AWS")
    monkeypatch.setattr(
        "claude_planner.interview.extract_new_facts", lambda **kw: {"hosting": "AWS"}
    )

    role_2 = InterviewRole(id="role-2", display_name="Role 2", persona="p", topics=["t"], goal="g")
    runner = InterviewRunner(project_name="P", client_name="C", profiles=[], intake_path=None)
    runner.run([ROLE, role_2])

    assert runner.state.facts == {"hosting": "AWS"}
    assert "hosting: AWS" not in calls[0]
    assert "hosting: AWS" in calls[1]


def test_scale_assessment_after_architect_is_injected_into_qa_stage(monkeypatch):
    """Moduł 3 (Agentic Routing): skala oceniona po etapie Architekta musi wylądować
    jako instrukcja warunkowa w system prompcie etapu qa-devops-ux, i tylko tam."""
    calls = []

    def make_session(**kwargs):
        calls.append(kwargs["system_prompt"])
        return FakeSession([_turn("done", summary=f"summary {len(calls)}")])

    monkeypatch.setattr("claude_planner.interview.ClaudeSession", make_session)
    monkeypatch.setattr("claude_planner.interview.Prompt.ask", lambda *a, **k: "odpowiedź")
    monkeypatch.setattr(
        "claude_planner.interview.assess_project_scale",
        lambda *a, **k: (ProjectScale.MICRO, "mały zakres, jeden deweloper"),
    )

    architect_role = InterviewRole(
        id="architect", display_name="Architekt", persona="p", topics=["t"], goal="g"
    )
    qa_role = InterviewRole(
        id="qa-devops-ux", display_name="QA", persona="p", topics=["t"], goal="g"
    )
    runner = InterviewRunner(project_name="P", client_name="C", profiles=[], intake_path=None)
    runner.run([architect_role, qa_role])

    assert runner.state.scale == ProjectScale.MICRO
    assert "Skala projektu to: Micro" not in calls[0]
    assert "Skala projektu to: Micro" in calls[1]
    assert "Zignoruj pytania o architekturę chmurową" in calls[1]


def test_fatigue_circuit_breaker_triggers_rescue_and_confirms_skip(monkeypatch):
    """Moduł 4: po 3 zbywających odpowiedziach agent musi zapytać o pominięcie etapu
    (RESCUE_MESSAGE); potwierdzenie użytkownika kończy etap, a same zbywające
    odpowiedzi liczą się do transkryptu, ale potwierdzenie "tak" już nie."""
    from claude_planner.fatigue import RESCUE_MESSAGE

    script = [
        _turn("question", question="Q1?"),
        _turn("question", question="Q2?"),
        _turn("question", question="Q3?"),
        _turn("question", question=RESCUE_MESSAGE),
        _turn("done", summary="Zakończono przez circuit breaker zmęczenia."),
    ]
    monkeypatch.setattr(
        "claude_planner.interview.ClaudeSession", lambda **kw: FakeSession(script)
    )
    answers = iter(["pomiń", "nie wiem", "zostaw to", "tak"])
    monkeypatch.setattr("claude_planner.interview.Prompt.ask", lambda *a, **k: next(answers))

    runner = InterviewRunner(project_name="P", client_name="C", profiles=[], intake_path=None)
    stages = runner.run([ROLE])

    assert runner.fatigue.breaker_tripped is True
    assert runner.state.fatigue_triggered is True
    assert stages[0].summary == "Zakończono przez circuit breaker zmęczenia."
    assert len(stages[0].qa) == 3


def test_stage_failure_propagates_and_preserves_earlier_completed_stages(monkeypatch):
    """Etap, którego nie udało się przeprowadzić (błąd Claude), musi przerwać cały
    wywiad zamiast fabrykować pusty/domyślny summary — ale to, co zebrano w
    poprzednich, zakończonych etapach, powinno zostać w `runner.completed_stages`."""

    class FailingSession:
        def __init__(self, **kwargs):
            pass

        def send(self, prompt):
            raise ClaudeCLIError("Claude nie odpowiedział")

    call_count = {"n": 0}

    def make_session(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return FakeSession([_turn("done", summary="Etap 1 zakończony poprawnie.")])
        return FailingSession(**kwargs)

    monkeypatch.setattr("claude_planner.interview.ClaudeSession", make_session)
    monkeypatch.setattr("claude_planner.interview.Prompt.ask", lambda *a, **k: "odpowiedź")

    role_2 = InterviewRole(id="role-2", display_name="Role 2", persona="p", topics=["t"], goal="g")
    runner = InterviewRunner(project_name="P", client_name="C", profiles=[], intake_path=None)

    with pytest.raises(ClaudeCLIError):
        runner.run([ROLE, role_2])

    assert len(runner.completed_stages) == 1
    assert runner.completed_stages[0].summary == "Etap 1 zakończony poprawnie."
