"""Sekwencyjny wywiad prowadzony per rola (PM/BA -> Architekt -> Dev -> QA/DevOps/UX).

Dla każdej roli otwierana jest osobna, kontynuowana sesja `claude -p`. Claude
zadaje po jednym pytaniu na turę, a odpowiedzi wpisuje człowiek w terminalu.
Odpowiedzi Claude są wymuszane jako JSON (przez --json-schema), żeby Python
mógł niezawodnie rozróżnić "kolejne pytanie" od "koniec etapu".
"""

from __future__ import annotations

import json

from rich.console import Console
from rich.prompt import Prompt

from claude_planner.claude_client import READ_ONLY_TOOLS, ClaudeCLIError, ClaudeSession
from claude_planner.models import (
    InterviewAnswer,
    InterviewRole,
    InterviewStageResult,
    StackProfile,
)

MAX_TURNS_PER_STAGE = 12
END_COMMANDS = {"koniec", "/koniec", "/done", "done", "/skip"}

TURN_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["question", "done"]},
        "question": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["action"],
}


def _build_stage_system_prompt(
    role: InterviewRole,
    project_name: str,
    client_name: str,
    profiles: list[StackProfile],
    previous_summaries: str,
) -> str:
    profile_lines = (
        "\n".join(f"- {p.name}: {p.description.strip()}" for p in profiles)
        or "- (brak wybranych profili)"
    )
    topics = "\n".join(f"- {t}" for t in role.topics)
    return f"""Jesteś: {role.persona}

Prowadzisz jeden etap discovery interview dla projektu software house'u.
Projekt: {project_name} (klient: {client_name})

Wybrane profile technologiczne:
{profile_lines}

Ustalenia z poprzednich etapów wywiadu (kontekst — nie powtarzaj tych pytań):
{previous_summaries or "(brak, to pierwszy etap)"}

Tematy, które musisz poruszyć w tym etapie:
{topics}

Cel etapu: {role.goal}

ZASADY:
- Zadawaj TYLKO JEDNO pytanie na turę, konkretne, w języku polskim.
- Dopytuj o konkrety; nie akceptuj biernie ogólników bez treści (np. "szybko i tanio").
- Jeśli w folderze materiałów (intake) są pliki istotne dla Twoich tematów, przejrzyj
  je najpierw narzędziami Read/Glob/Grep, zanim zapytasz o coś co już tam jest opisane.
- Gdy zebrałeś wystarczające informacje ze wszystkich tematów (albo user poprosi
  o zakończenie etapu), zakończ etap.
- Odpowiadaj WYŁĄCZNIE w formacie JSON zgodnym z dostarczonym schematem:
  {{"action": "question", "question": "..."}} albo
  {{"action": "done", "summary": "zwięzłe podsumowanie ustaleń tego etapu po polsku,
  w punktach, gotowe do wykorzystania przy generowaniu dokumentacji projektu"}}.
"""


def _parse_turn(raw_text: str) -> dict:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        # Fallback: Claude nie trzymał się schematu — traktujemy cały tekst jako pytanie.
        return {"action": "question", "question": raw_text.strip()}


class InterviewRunner:
    """Prowadzi jeden pełny wywiad (wszystkie role) dla projektu."""

    def __init__(
        self,
        *,
        project_name: str,
        client_name: str,
        profiles: list[StackProfile],
        intake_path: str | None,
        model: str | None = None,
        console: Console | None = None,
    ) -> None:
        self.project_name = project_name
        self.client_name = client_name
        self.profiles = profiles
        self.intake_path = intake_path
        self.model = model
        self.console = console or Console()

    def run(self, roles: list[InterviewRole]) -> list[InterviewStageResult]:
        stages: list[InterviewStageResult] = []
        summaries_so_far = ""
        for role in roles:
            stage = self._run_stage(role, summaries_so_far)
            stages.append(stage)
            if stage.summary:
                summaries_so_far += f"\n\n### {role.display_name}\n{stage.summary}"
        return stages

    def _run_stage(self, role: InterviewRole, previous_summaries: str) -> InterviewStageResult:
        console = self.console
        console.rule(f"[bold cyan]{role.display_name}")
        system_prompt = _build_stage_system_prompt(
            role, self.project_name, self.client_name, self.profiles, previous_summaries
        )
        add_dirs = [self.intake_path] if self.intake_path else None
        session = ClaudeSession(
            system_prompt=system_prompt,
            add_dirs=add_dirs,
            allowed_tools=READ_ONLY_TOOLS,
            model=self.model,
            json_schema=TURN_JSON_SCHEMA,
        )

        qa: list[InterviewAnswer] = []
        summary = ""
        prompt = (
            "Rozpocznij ten etap wywiadu i zadaj pierwsze pytanie zgodnie z zasadami "
            "podanymi w system prompcie."
        )
        forced_end = False

        for _ in range(MAX_TURNS_PER_STAGE):
            try:
                result = session.send(prompt)
            except ClaudeCLIError as exc:
                console.print(f"[red]Błąd wywołania Claude: {exc}[/red]")
                break

            turn = _parse_turn(result.text)
            action = turn.get("action")

            if action == "done" or forced_end:
                summary = turn.get("summary", "") or "\n".join(
                    f"- {item.question}: {item.answer}" for item in qa
                )
                break

            question = turn.get("question", "").strip()
            if not question:
                break
            console.print(f"[bold green]{role.display_name}:[/bold green] {question}")
            answer = Prompt.ask("[bold]Twoja odpowiedź[/bold]")
            if answer.strip().lower() in END_COMMANDS:
                forced_end = True
                prompt = (
                    "Użytkownik poprosił o zakończenie tego etapu wywiadu teraz. "
                    "Zwróć action='done' z podsumowaniem tego, co już ustalono "
                    "(nawet jeśli niepełne)."
                )
                continue

            qa.append(InterviewAnswer(role_id=role.id, question=question, answer=answer))
            prompt = f"Odpowiedź użytkownika: {answer}"

        if not summary:
            summary = "\n".join(f"- {item.question}: {item.answer}" for item in qa) or (
                "(brak odpowiedzi zebranych na tym etapie)"
            )

        return InterviewStageResult(
            role_id=role.id, display_name=role.display_name, qa=qa, summary=summary
        )
