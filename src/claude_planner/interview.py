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

from claude_planner.claude_client import READ_ONLY_TOOLS, ClaudeSession
from claude_planner.fatigue import RESCUE_MESSAGE, FatigueTracker, is_affirmative, is_dismissive
from claude_planner.models import (
    InterviewAnswer,
    InterviewRole,
    InterviewStageResult,
    ProjectState,
    StackProfile,
)
from claude_planner.progress import thinking
from claude_planner.scale import assess_project_scale, qa_scale_instruction
from claude_planner.state import apply_new_facts, extract_new_facts, render_state_snapshot

MAX_TURNS_PER_STAGE = 12
MAX_HISTORY_TURNS_IN_PROMPT = 6
END_COMMANDS = {"koniec", "/koniec", "/done", "done", "/skip"}
SCALE_ROUTED_ROLE_ID = "qa-devops-ux"
SCALE_ASSESSMENT_AFTER_ROLE_ID = "architect"

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
    state_snapshot: str,
    *,
    extra_instructions: str = "",
    fatigue_notice: bool = False,
) -> str:
    profile_lines = (
        "\n".join(f"- {p.name}: {p.description.strip()}" for p in profiles)
        or "- (brak wybranych profili)"
    )
    topics = "\n".join(f"- {t}" for t in role.topics)
    scale_block = f"\n{extra_instructions}\n" if extra_instructions else ""
    fatigue_block = (
        "\nUWAGA (Circuit Breaker zmęczenia): użytkownik już wcześniej w tym wywiadzie "
        "wielokrotnie zbywał pytania. Zadawaj WYŁĄCZNIE pytania absolutnie kluczowe, "
        "krócej i rzadziej dopytuj o detale, i bądź gotów wcześniej zaproponować "
        "zakończenie etapu.\n"
        if fatigue_notice
        else ""
    )
    return f"""Jesteś: {role.persona}

Prowadzisz jeden etap discovery interview dla projektu software house'u.
Projekt: {project_name} (klient: {client_name})

Wybrane profile technologiczne:
{profile_lines}

--- GLOBALNA PAMIĘĆ WSPÓŁDZIELONA (Project State, Moduł 1) ---
Oto dotychczas zebrane informacje o projekcie, ustalone przez WSZYSTKIE etapy wywiadu
do tej pory (nie tylko ten):
{state_snapshot}

ŻELAZNA ZASADA: NIGDY nie pytaj o kwestie, które są już w powyższym stanie. Jeśli
czegoś brakuje albo jest niejasne, dopytaj o KONKRETNY brakujący szczegół — nie
duplikuj pytań, które już padły (ani w tym etapie, ani w żadnym poprzednim).
--- KONIEC GLOBALNEJ PAMIĘCI ---

Pełne podsumowania poprzednich etapów wywiadu (dodatkowy kontekst narracyjny):
{previous_summaries or "(brak, to pierwszy etap)"}
{scale_block}{fatigue_block}
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


def _recent_transcript(qa: list[InterviewAnswer], limit: int = MAX_HISTORY_TURNS_IN_PROMPT) -> str:
    """Moduł 2: okno ostatnich wymian w TYM etapie, re-wstrzykiwane do każdej tury.

    `ClaudeSession` już utrzymuje pełną historię przez `claude --resume`, ale to
    dodatkowe, jawne (i zamierzenie ograniczone oknem, żeby nie rozdmuchiwać tokenów)
    przypomnienie zabezpiecza przed sytuacją, w której agent "gubi" fakt podany
    2-3 wiadomości wcześniej we własnej turze i pyta o niego ponownie.
    """
    recent = qa[-limit:]
    if not recent:
        return ""
    lines = "\n".join(f"P: {item.question}\nO: {item.answer}" for item in recent)
    return (
        "\n\nPrzypomnienie — ostatnie wymiany w TYM etapie (NIE pytaj o nie ponownie):\n"
        f"{lines}"
    )


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
        self.completed_stages: list[InterviewStageResult] = []
        self.state = ProjectState()
        self.fatigue = FatigueTracker()

    def run(self, roles: list[InterviewRole]) -> list[InterviewStageResult]:
        """Prowadzi wszystkie etapy po kolei. Jeśli któryś etap padnie (ClaudeCLIError),
        wyjątek leci dalej zamiast fabrykować dokumentację z pustego etapu — to, co zdążyło
        się zebrać do tego momentu, zostaje w `self.completed_stages` dla wywołującego."""
        summaries_so_far = ""
        for role in roles:
            extra_instructions = (
                qa_scale_instruction(self.state.scale) if role.id == SCALE_ROUTED_ROLE_ID else ""
            )
            stage = self._run_stage(role, summaries_so_far, extra_instructions)
            self.completed_stages.append(stage)
            if stage.summary:
                summaries_so_far += f"\n\n### {role.display_name}\n{stage.summary}"
            if role.id == SCALE_ASSESSMENT_AFTER_ROLE_ID and self.state.scale is None:
                self._assess_scale(summaries_so_far)
        return self.completed_stages

    def _assess_scale(self, summaries_so_far: str) -> None:
        """Moduł 3 (Agentic Routing): po etapie Architekta oceń skalę projektu raz,
        żeby wstrzyknąć ją jako instrukcję warunkową do kolejnego etapu (QA/DevOps)."""
        context = (
            f"Projekt: {self.project_name} (klient: {self.client_name})\n\n"
            f"Ustalenia z dotychczasowych etapów wywiadu:\n{summaries_so_far}"
        )
        scale, justification = assess_project_scale(context, model=self.model)
        self.state.scale = scale
        self.state.scale_justification = justification
        self.console.print(
            f"[dim]Orchestrator: oceniona skala projektu = {scale.value} ({justification})[/dim]"
        )

    def _run_stage(
        self, role: InterviewRole, previous_summaries: str, extra_instructions: str = ""
    ) -> InterviewStageResult:
        console = self.console
        console.rule(f"[bold cyan]{role.display_name}")
        system_prompt = _build_stage_system_prompt(
            role,
            self.project_name,
            self.client_name,
            self.profiles,
            previous_summaries,
            render_state_snapshot(self.state),
            extra_instructions=extra_instructions,
            fatigue_notice=self.fatigue.breaker_tripped,
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
        awaiting_rescue_confirmation = False

        for _ in range(MAX_TURNS_PER_STAGE):
            # ClaudeCLIError celowo NIE jest tu łapany: etap, którego nie udało się
            # przeprowadzić, nie może cicho zamienić się w pusty/zmyślony fallback
            # (patrz `_run_stage`'s summary fallback poniżej) trafiający potem do
            # dokumentacji projektu. Wywołujący (`scaffold.run_init`) łapie ten wyjątek
            # i zapisuje to, co już zebrano, zanim przerwie.
            with thinking(console, f"{role.display_name} zastanawia się"):
                result = session.send(prompt)

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

            if awaiting_rescue_confirmation:
                # Moduł 4: odpowiedź na pytanie ratunkowe circuit breakera, nie na
                # normalne pytanie merytoryczne — nie traktujemy jej jako Q&A/fakt.
                awaiting_rescue_confirmation = False
                if is_affirmative(answer):
                    forced_end = True
                    prompt = (
                        "Użytkownik potwierdził pominięcie reszty tego etapu. Zwróć "
                        "action='done' z podsumowaniem tego, co już ustalono (nawet "
                        "jeśli niepełne)."
                    )
                else:
                    prompt = (
                        "Użytkownik NIE chce pomijać etapu — kontynuuj normalnie, zadaj "
                        f"kolejne najważniejsze pytanie. Odpowiedź użytkownika: {answer}"
                    )
                continue

            qa.append(InterviewAnswer(role_id=role.id, question=question, answer=answer))

            # Moduł 1: wyciągnij i scal nowe fakty do globalnego stanu (pomijamy
            # zbywające odpowiedzi — nie niosą żadnego faktu wartego ekstrakcji).
            if not is_dismissive(answer):
                new_facts = extract_new_facts(
                    role_display_name=role.display_name,
                    question=question,
                    answer=answer,
                    state=self.state,
                    model=self.model,
                )
                if new_facts:
                    apply_new_facts(self.state, role.id, new_facts)

            # Moduł 4: fatigue circuit breaker.
            if self.fatigue.record(answer):
                self.state.fatigue_triggered = True
                awaiting_rescue_confirmation = True
                prompt = (
                    "UWAGA (circuit breaker zmęczenia użytkownika): użytkownik "
                    "wielokrotnie zbywał pytania. Zamiast zadawać kolejne pytanie "
                    "merytoryczne, zwróć action='question' z DOKŁADNIE tą treścią (nic "
                    f'nie zmieniaj, nic nie dodawaj): "{RESCUE_MESSAGE}"'
                )
            else:
                prompt = f"Odpowiedź użytkownika: {answer}{_recent_transcript(qa)}"

        if not summary:
            summary = "\n".join(f"- {item.question}: {item.answer}" for item in qa) or (
                "(brak odpowiedzi zebranych na tym etapie)"
            )

        return InterviewStageResult(
            role_id=role.id, display_name=role.display_name, qa=qa, summary=summary
        )
