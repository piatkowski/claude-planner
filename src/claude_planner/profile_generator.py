"""Generowanie nowego profilu stacku przy pomocy Claude (`claude -p`)."""

from __future__ import annotations

import json

import yaml
from pydantic import ValidationError

from claude_planner.claude_client import ClaudeCLIError, one_shot
from claude_planner.models import StackProfile

PROFILE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "languages": {"type": "array", "items": {"type": "string"}},
        "frameworks": {"type": "array", "items": {"type": "string"}},
        "setup_commands": {"type": "array", "items": {"type": "string"}},
        "extra_agents": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "focus": {"type": "string"},
                },
                "required": ["id", "name", "description", "focus"],
            },
        },
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "when_to_use": {"type": "string"},
                    "guidance": {"type": "string"},
                },
                "required": ["name", "description", "when_to_use", "guidance"],
            },
        },
        "conventions_hints": {"type": "string"},
        "testing_hints": {"type": "string"},
        "claude_hints": {"type": "string"},
    },
    "required": [
        "name",
        "description",
        "languages",
        "frameworks",
        "setup_commands",
        "extra_agents",
        "skills",
        "conventions_hints",
        "testing_hints",
        "claude_hints",
    ],
}

PROMPT_TEMPLATE = """Jesteś doświadczonym Architektem/Tech Leadem software house'u,
który projektuje profil technologiczny dla generatora środowisk Claude Code
(claude-planner). Profil dotyczy stacku: "{stack_description}".

Wygeneruj kompletny profil, po polsku, w stylu analogicznym do istniejących
profili tego narzędzia (konkretne, praktyczne wskazówki, nie ogólniki):

- name: krótka, czytelna nazwa profilu.
- description: 1-3 zdania — czym jest ten stack i kiedy się go wybiera.
- languages / frameworks: realne technologie tego stacku.
- setup_commands: konkretne komendy bootstrapujące toolchain/zależności tego
  stacku, żeby po ich uruchomieniu Claude Code mógł uruchomić code
  intelligence (LSP) dla tego języka. NIE podawaj przypiętych numerów wersji
  pakietów w tych komendach (np. "npm install", "composer install",
  "pip install -e '.[dev]'" — bez konkretnych wersji, menedżer pakietów sam
  dobierze aktualną).
- extra_agents: 0-2 dodatkowych agentów specyficznych dla tego stacku (poza
  bazowymi rolami Product Manager/Architekt/Developer/QA, które są wspólne
  dla wszystkich profili) — id (kebab-case, unikalny), name, description, focus.
- skills: 1-3 skille (konwencje) specyficzne dla tego stacku — name
  (kebab-case), description, when_to_use, guidance.
- conventions_hints, testing_hints, claude_hints: zwięzłe, konkretne akapity
  (odpowiednio: konwencje struktury/kodu, strategia testów, dodatkowy
  kontekst dla Claude przy generowaniu dokumentacji projektu).

Zwróć WYŁĄCZNIE JSON zgodny z dostarczonym schematem.
"""

FIELD_ORDER = [
    "id",
    "name",
    "description",
    "languages",
    "frameworks",
    "extra_agents",
    "skills",
    "setup_commands",
    "conventions_hints",
    "testing_hints",
    "claude_hints",
]


def generate_profile(stack_description: str, profile_id: str, *, model: str | None = None) -> StackProfile:
    """Woła Claude, żeby zaprojektował nowy profil stacku, i zwraca go jako `StackProfile`."""
    prompt = PROMPT_TEMPLATE.format(stack_description=stack_description)
    raw = one_shot(prompt, allowed_tools=[], model=model, json_schema=PROFILE_JSON_SCHEMA)
    try:
        data = json.loads(raw)
        data["id"] = profile_id
        return StackProfile.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ClaudeCLIError(
            f"Claude zwrócił niepoprawne dane profilu ({exc}).\nSurowa odpowiedź:\n{raw}"
        ) from exc


def profile_to_yaml(profile: StackProfile) -> str:
    data = profile.model_dump()
    ordered = {key: data[key] for key in FIELD_ORDER if key in data}
    return yaml.safe_dump(ordered, allow_unicode=True, sort_keys=False)
