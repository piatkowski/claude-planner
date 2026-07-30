import json

from claude_planner.claude_client import ClaudeTurnResult
from claude_planner.interview import InterviewRunner
from claude_planner.models import InterviewRole


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
