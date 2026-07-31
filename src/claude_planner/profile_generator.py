"""Generowanie nowego profilu stacku przy pomocy Claude (`claude -p`).

Świadomie NIE korzystamy z `--json-schema` (patrz `claude_client.one_shot`):
w praktyce ten mechanizm CLI potrafił wchodzić w wielominutową, agentową
pętlę dopasowywania odpowiedzi do schematu i kończyć się timeoutem albo
`error_max_structured_output_retries` — dla użytkownika wyglądało to jak
zawieszenie się `profiles create`. Zamiast tego prosimy model wprost o surowy
JSON w treści promptu i sami, po stronie Pythona, parsujemy/walidujemy
odpowiedź — a jeśli model się pomyli, ponawiamy tylko lekki, zwykły prompt
(nie kosztowną pętlę CLI).
"""

from __future__ import annotations

import json
import re

import yaml
from pydantic import ValidationError

from claude_planner.claude_client import ClaudeCLIError, one_shot
from claude_planner.models import StackProfile

MAX_GENERATION_ATTEMPTS = 3
GENERATION_TIMEOUT_SECONDS = 120

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

Zwróć WYŁĄCZNIE surowy JSON (bez markdown, bez bloków ```, bez żadnego
komentarza przed ani po) o dokładnie takim kształcie:

{{
  "name": "...",
  "description": "...",
  "languages": ["..."],
  "frameworks": ["..."],
  "setup_commands": ["..."],
  "extra_agents": [{{"id": "...", "name": "...", "description": "...", "focus": "..."}}],
  "skills": [{{"name": "...", "description": "...", "when_to_use": "...", "guidance": "..."}}],
  "conventions_hints": "...",
  "testing_hints": "...",
  "claude_hints": "..."
}}
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

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


def _extract_json_object(raw: str) -> dict:
    """Parsuje JSON z odpowiedzi modelu, tolerując otoczenie blokiem ``` albo
    prozą przed/po (mimo instrukcji część modeli i tak to dodaje)."""
    text = raw.strip()
    fence_match = _CODE_FENCE_RE.match(text)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise json.JSONDecodeError("Brak obiektu JSON w odpowiedzi", text, 0)
    return json.loads(text[start : end + 1])


def generate_profile(stack_description: str, profile_id: str, *, model: str | None = None) -> StackProfile:
    """Woła Claude, żeby zaprojektował nowy profil stacku, i zwraca go jako `StackProfile`.

    Każda próba to zwykły, krótki prompt (bez `--json-schema`) — jeśli model
    zwróci coś, co nie parsuje się do poprawnego profilu, ponawiamy do
    `MAX_GENERATION_ATTEMPTS` razy zanim zgłosimy błąd.
    """
    prompt = PROMPT_TEMPLATE.format(stack_description=stack_description)
    last_error: Exception | None = None
    last_raw = ""

    for _ in range(MAX_GENERATION_ATTEMPTS):
        last_raw = one_shot(prompt, allowed_tools=[], model=model, timeout=GENERATION_TIMEOUT_SECONDS)
        try:
            data = _extract_json_object(last_raw)
            data["id"] = profile_id
            return StackProfile.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc

    raise ClaudeCLIError(
        f"Claude zwrócił niepoprawne dane profilu po {MAX_GENERATION_ATTEMPTS} "
        f"próbach ({last_error}).\nOstatnia surowa odpowiedź:\n{last_raw}"
    )


def profile_to_yaml(profile: StackProfile) -> str:
    data = profile.model_dump()
    ordered = {key: data[key] for key in FIELD_ORDER if key in data}
    return yaml.safe_dump(ordered, allow_unicode=True, sort_keys=False)
