"""Generowanie kompletnego środowiska docs/ + .claude/ na podstawie ProjectBrief."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

from claude_planner.claude_client import READ_ONLY_TOOLS, one_shot
from claude_planner.models import ProjectBrief, StackProfile
from claude_planner.roles import INTERVIEW_ROLES
from claude_planner.templating import render
from claude_planner.textutils import slugify

ADR_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "context": {"type": "string"},
                    "decision": {"type": "string"},
                    "consequences": {"type": "string"},
                },
                "required": ["title", "context", "decision", "consequences"],
            },
        }
    },
    "required": ["decisions"],
}

BASE_COMMANDS = [
    ("new-adr", "Utwórz nowy Architecture Decision Record", "command_new_adr.j2"),
    ("update-roadmap", "Zaktualizuj roadmapę na podstawie bieżącego stanu prac", "command_update_roadmap.j2"),
    ("update-state", "Nadpisz state.md aktualnym stanem projektu", "command_update_state.j2"),
    ("log-decision", "Zapisz szybką decyzję bez pełnego ADR", "command_log_decision.j2"),
    ("daily-standup", "Wygeneruj krótkie podsumowanie standup", "command_daily_standup.j2"),
    ("sprint-review", "Podsumuj zakończony sprint/etap względem roadmapy", "command_sprint_review.j2"),
]


def _context_block(brief: ProjectBrief, profiles: list[StackProfile]) -> str:
    profile_lines = "\n".join(f"- {p.name}: {p.description.strip()}" for p in profiles)
    stages_text = "\n\n".join(
        f"### {stage.display_name}\n{stage.summary}" for stage in brief.stages
    )
    return f"""Projekt: {brief.project_name}
Klient: {brief.client_name}

Profile technologiczne:
{profile_lines}

Streszczenie materiałów od klienta (intake):
{brief.intake_summary}

Ustalenia z wywiadu discovery:
{stages_text}
"""


def _profile_hints(profiles: list[StackProfile], attr: str) -> str:
    lines = []
    for profile in profiles:
        hint = getattr(profile, attr, "").strip()
        if hint:
            lines.append(f"- [{profile.name}] {hint}")
    return "\n".join(lines) or "(brak specyficznych wskazówek z profili)"


def _ask(brief: ProjectBrief, profiles: list[StackProfile], instruction: str, *, model=None) -> str:
    prompt = f"{_context_block(brief, profiles)}\n\n---\n\n{instruction}"
    return one_shot(prompt, allowed_tools=READ_ONLY_TOOLS, model=model).strip() + "\n"


DOC_INSTRUCTIONS = {
    "vision.md": """Napisz dokument wizji produktu (`docs/vision.md`) w Markdown, po polsku.
Zawrzyj: problem/kontekst biznesowy, grupę docelową i interesariuszy, zakres MVP vs
pełną wizję, sposób mierzenia sukcesu (KPI), kluczowe ryzyka biznesowe.
Zwróć WYŁĄCZNIE treść dokumentu zaczynając od nagłówka `#`, bez komentarzy typu
"oto dokument".""",
    "prd.md": """Napisz backlog produktu (`docs/prd.md`) w Markdown, po polsku, jako listę
epików podzielonych na historyjki użytkownika (`Jako ..., chcę ..., żeby ...`) z grubym
oszacowaniem priorytetu (Must/Should/Could). Zwróć WYŁĄCZNIE treść dokumentu.""",
    "roadmap.md": """Napisz roadmapę projektu (`docs/roadmap.md`) w Markdown, po polsku,
podzieloną na fazy/kamienie milowe (np. Discovery, MVP, kolejne iteracje) z grubym
zakresem czasowym i zależnościami między fazami. Zwróć WYŁĄCZNIE treść dokumentu.""",
    "definition-of-done.md": """Napisz Definition of Done (`docs/definition-of-done.md`)
w Markdown, po polsku — konkretną, sprawdzalną listę kryteriów, które musi spełnić
zadanie/feature żeby uznać je za ukończone w tym projekcie. Zwróć WYŁĄCZNIE treść
dokumentu.""",
}


def generate_vision(brief, profiles, *, model=None) -> str:
    return _ask(brief, profiles, DOC_INSTRUCTIONS["vision.md"], model=model)


def generate_prd(brief, profiles, *, model=None) -> str:
    return _ask(brief, profiles, DOC_INSTRUCTIONS["prd.md"], model=model)


def generate_roadmap(brief, profiles, *, model=None) -> str:
    return _ask(brief, profiles, DOC_INSTRUCTIONS["roadmap.md"], model=model)


def generate_definition_of_done(brief, profiles, *, model=None) -> str:
    return _ask(brief, profiles, DOC_INSTRUCTIONS["definition-of-done.md"], model=model)


def generate_coding_standards(brief, profiles, *, model=None) -> str:
    hints = _profile_hints(profiles, "conventions_hints")
    claude_hints = _profile_hints(profiles, "claude_hints")
    instruction = f"""Napisz standardy kodowania (`docs/coding-standards.md`) w Markdown,
po polsku, dopasowane do wybranych profili technologicznych. Uwzględnij wskazówki
z profili:
{hints}

Dodatkowy kontekst dla wybranych profili:
{claude_hints}

Dodaj też sekcję "Zależności" z konkretną, stack-specyficzną instrukcją: przy
dodawaniu nowej zależności NIGDY nie zgaduj (nie halucynuj) numeru wersji z
pamięci — zawsze sprawdź realnie dostępną wersję komendą menedżera pakietów
właściwą dla tego stacku (np. `npm view <pkg> versions`, `pip index versions
<pkg>`, `composer show -a <pkg>`, `dart pub deps`) albo zapytaj użytkownika o
dokładną wersję.

Zwróć WYŁĄCZNIE treść dokumentu."""
    return _ask(brief, profiles, instruction, model=model)


def generate_test_strategy(brief, profiles, *, model=None) -> str:
    hints = _profile_hints(profiles, "testing_hints")
    instruction = f"""Napisz strategię testów (`docs/test-strategy.md`) w Markdown, po
polsku, dopasowaną do wybranych profili technologicznych. Uwzględnij wskazówki z
profili:
{hints}

Zwróć WYŁĄCZNIE treść dokumentu."""
    return _ask(brief, profiles, instruction, model=model)


def generate_adrs(brief, profiles, *, model=None) -> list[dict]:
    instruction = """Na podstawie ustaleń z wywiadu (szczególnie etapu Architekt/Tech
Lead) wypisz listę decyzji architektonicznych, które warto udokumentować jako ADR
na starcie projektu (np. wybór głównych technologii, kluczowe wzorce integracji,
model danych, strategia wdrożenia). Zwróć od 1 do 8 decyzji — tylko takie, które
faktycznie mają wysoki koszt zmiany; nie twórz ADR dla oczywistości."""
    prompt = f"{_context_block(brief, profiles)}\n\n---\n\n{instruction}"
    raw = one_shot(
        prompt,
        allowed_tools=READ_ONLY_TOOLS,
        model=model,
        json_schema=ADR_LIST_SCHEMA,
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data.get("decisions", [])


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_adrs(docs_dir: Path, project_name: str, decisions: list[dict]) -> None:
    adr_dir = docs_dir / "adr"
    _write(adr_dir / "template.md", render("adr_template.j2"))
    today = date.today().isoformat()
    adr_meta = []
    for i, decision in enumerate(decisions, start=1):
        number = f"{i:04d}"
        title = decision.get("title", f"Decyzja {number}").strip()
        slug = slugify(title, fallback="decyzja")
        filename = f"{number}-{slug}.md"
        content = render(
            "adr_entry.j2",
            number=number,
            title=title,
            date=today,
            context=decision.get("context", ""),
            decision=decision.get("decision", ""),
            consequences=decision.get("consequences", ""),
        )
        _write(adr_dir / filename, content)
        adr_meta.append({"number": number, "title": title, "filename": filename})
    _write(
        adr_dir / "README.md",
        render("adr_index.j2", project_name=project_name, adrs=adr_meta),
    )


def _write_base_agents(claude_dir: Path, brief: ProjectBrief) -> list[dict]:
    stage_by_role = {stage.role_id: stage for stage in brief.stages}
    written = []
    for role in INTERVIEW_ROLES:
        stage = stage_by_role.get(role.id)
        project_context = stage.summary if stage else "(wywiad dla tej roli nie został przeprowadzony)"
        body = f"""{role.persona}

## Zakres odpowiedzialności w tym projekcie

{chr(10).join(f"- {t}" for t in role.topics)}

## Kontekst projektu ({brief.project_name})

{project_context}
"""
        content = render(
            "agent.j2", agent_id=role.id, description=role.goal, body=body.strip() + "\n"
        )
        _write(claude_dir / "agents" / f"{role.id}.md", content)
        written.append({"agent_id": role.id, "description": role.goal})
    return written


def _write_profile_agents(claude_dir: Path, profiles: list[StackProfile]) -> list[dict]:
    written = []
    for profile in profiles:
        for agent in profile.extra_agents:
            body = f"{agent.description}\n\n## Na czym się skupiasz\n\n{agent.focus}\n"
            content = render("agent.j2", agent_id=agent.id, description=agent.description, body=body)
            _write(claude_dir / "agents" / f"{agent.id}.md", content)
            written.append({"agent_id": agent.id, "description": agent.description})
    return written


def _write_profile_skills(claude_dir: Path, profiles: list[StackProfile]) -> list[dict]:
    written = []
    for profile in profiles:
        for skill in profile.skills:
            content = render(
                "skill.j2",
                skill_id=skill.name,
                description=skill.description,
                when_to_use=skill.when_to_use,
                guidance=skill.guidance,
            )
            _write(claude_dir / "skills" / skill.name / "SKILL.md", content)
            written.append(
                {
                    "skill_id": skill.name,
                    "description": skill.description,
                    "when_to_use": skill.when_to_use,
                    "profile_name": profile.name,
                }
            )
    return written


def _write_commands(claude_dir: Path) -> list[dict]:
    written = []
    for command_id, description, template_name in BASE_COMMANDS:
        _write(claude_dir / "commands" / f"{command_id}.md", render(template_name))
        written.append({"command_id": command_id, "description": description})
    return written


SETUP_COMMAND_DESCRIPTION = (
    "Zainstaluj toolchain/zależności stacku (wymagane dla code intelligence / LSP)"
)


def _write_setup_command(claude_dir: Path, profiles: list[StackProfile]) -> dict:
    content = render("command_setup_dev_environment.j2", profiles=profiles)
    _write(claude_dir / "commands" / "setup-dev-environment.md", content)
    return {"command_id": "setup-dev-environment", "description": SETUP_COMMAND_DESCRIPTION}


def _write_settings(claude_dir: Path) -> None:
    hook_script = render("hook_check_pinned_dependency.py.j2")
    _write(claude_dir / "hooks" / "check-pinned-dependency.py", hook_script)

    settings = {
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": (
                                "echo '--- state.md ---'; "
                                'sed -n "1,12p" "$CLAUDE_PROJECT_DIR/state.md" 2>/dev/null || true'
                            ),
                        }
                    ]
                }
            ],
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": (
                                'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/'
                                'check-pinned-dependency.py"'
                            ),
                        }
                    ],
                }
            ],
        }
    }
    _write(claude_dir / "settings.json", json.dumps(settings, indent=2, ensure_ascii=False) + "\n")


def generate_environment(
    brief: ProjectBrief,
    profiles: list[StackProfile],
    output_dir: Path,
    *,
    model: str | None = None,
    on_step: Callable[[str], None] | None = None,
) -> dict:
    """Generuje pełne środowisko w `output_dir`. Zwraca metadane wygenerowanych plików.

    `on_step` (opcjonalny) jest wołany z etykietą przed każdym z kilku kolejnych
    wywołań `claude`, które mogą trwać nawet kilka minut każde — pozwala UI
    pokazać, na którym dokumencie generowanie aktualnie stoi, zamiast milczeć
    przez cały czas trwania `generate_environment`.
    """
    docs_dir = output_dir / "docs"
    claude_dir = output_dir / ".claude"
    generated_at = date.today().isoformat()
    step = on_step or (lambda _label: None)

    step("docs/vision.md")
    _write(docs_dir / "vision.md", generate_vision(brief, profiles, model=model))
    step("docs/prd.md")
    _write(docs_dir / "prd.md", generate_prd(brief, profiles, model=model))
    step("docs/roadmap.md")
    _write(docs_dir / "roadmap.md", generate_roadmap(brief, profiles, model=model))
    step("docs/coding-standards.md")
    _write(
        docs_dir / "coding-standards.md",
        generate_coding_standards(brief, profiles, model=model),
    )
    step("docs/definition-of-done.md")
    _write(
        docs_dir / "definition-of-done.md",
        generate_definition_of_done(brief, profiles, model=model),
    )
    step("docs/test-strategy.md")
    _write(
        docs_dir / "test-strategy.md",
        generate_test_strategy(brief, profiles, model=model),
    )

    step("decyzje architektoniczne (ADR)")
    decisions = generate_adrs(brief, profiles, model=model)
    _write_adrs(docs_dir, brief.project_name, decisions)

    agents = _write_base_agents(claude_dir, brief) + _write_profile_agents(claude_dir, profiles)
    skills = _write_profile_skills(claude_dir, profiles)
    commands = _write_commands(claude_dir) + [_write_setup_command(claude_dir, profiles)]
    _write_settings(claude_dir)

    profile_names = ", ".join(p.name for p in profiles)
    _write(
        output_dir / "state.md",
        render(
            "state.j2",
            project_name=brief.project_name,
            generated_at=generated_at,
            profile_names=profile_names,
        ),
    )
    _write(
        output_dir / "CLAUDE.md",
        render(
            "claude_md.j2",
            project_name=brief.project_name,
            client_name=brief.client_name,
            generated_at=generated_at,
            profiles=profiles,
            agents=agents,
            commands=commands,
        ),
    )
    _write(
        output_dir / "README.md",
        render(
            "project_readme.j2",
            project_name=brief.project_name,
            client_name=brief.client_name,
            profiles=profiles,
        ),
    )
    _write(
        output_dir / "WORKFLOW.md",
        render(
            "workflow.j2",
            project_name=brief.project_name,
            client_name=brief.client_name,
            generated_at=generated_at,
            profiles=profiles,
            agents=agents,
            commands=commands,
            skills=skills,
            adr_count=len(decisions),
        ),
    )

    return {
        "docs": ["vision.md", "prd.md", "roadmap.md", "coding-standards.md",
                 "definition-of-done.md", "test-strategy.md"],
        "adr_count": len(decisions),
        "agents": [a["agent_id"] for a in agents],
        "commands": [c["command_id"] for c in commands],
        "skills": [s["skill_id"] for s in skills],
    }
