"""Moduł 1: globalna pamięć współdzielona (Blackboard pattern) między rolami wywiadu.

`ProjectState` (patrz `models.py`) jest jedynym źródłem prawdy o faktach ustalonych
do tej pory — niezależnie, która rola/etap je ustaliła. Przepływ:

1. Przed każdą turą agenta `interview._build_stage_system_prompt` wstrzykuje
   `render_state_snapshot(state)` do system promptu tej roli.
2. Po każdej odpowiedzi użytkownika `extract_new_facts` robi tanie, poboczne
   wywołanie LLM (bez narzędzi, JSON schema) ekstrahujące NOWE, atomowe fakty.
3. `apply_new_facts` scala je do globalnego stanu, żeby żadna kolejna rola (ani ta
   sama rola kilka pytań później) nie zapytała o to samo drugi raz.
"""

from __future__ import annotations

import json

from claude_planner.claude_client import one_shot
from claude_planner.models import ProjectState

FACT_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "description": (
                "Mapa klucz_faktu -> ustalona wartość. Tylko NOWE fakty, których nie ma "
                "jeszcze wśród znanych."
            ),
        }
    },
    "required": ["facts"],
}


def _extraction_prompt(
    role_display_name: str, question: str, answer: str, known_facts: dict[str, str]
) -> str:
    known = (
        "\n".join(f"- {key}: {value}" for key, value in known_facts.items()) or "(brak)"
    )
    return f"""Rola prowadząca wywiad: {role_display_name}
Pytanie zadane klientowi: {question}
Odpowiedź klienta: {answer}

Znane już fakty o projekcie (NIE zwracaj ich ponownie, nawet przeformułowanych):
{known}

Zadanie: wypisz WYŁĄCZNIE nowe, konkretne, atomowe fakty o projekcie ustalone w tej
odpowiedzi (np. "hosting": "AWS", "budzet": "50000 PLN", "grupa_docelowa": "B2C, ok.
300 SKU"). Klucze pisz w snake_case, po polsku bez ogonków, krótkie (1-3 słowa).
Jeśli odpowiedź nie wnosi żadnego nowego, konkretnego faktu (np. "nie wiem", "bez
znaczenia", ogólnik bez treści), zwróć pustą mapę. Zwróć WYŁĄCZNIE JSON zgodny ze
schematem, bez komentarzy."""


def extract_new_facts(
    *,
    role_display_name: str,
    question: str,
    answer: str,
    state: ProjectState,
    model: str | None = None,
) -> dict[str, str]:
    """Poboczne wywołanie LLM ekstrahujące nowe fakty z jednej wymiany pytanie/odpowiedź.

    Celowo bezstanowe i odporne na błędy: to wywołanie pomocnicze, nie krytyczny etap
    wywiadu — jeśli Claude jest niedostępny albo zwróci coś, czego nie da się
    sparsować, po prostu nie aktualizujemy stanu w tej turze zamiast przerywać wywiad.
    """
    prompt = _extraction_prompt(role_display_name, question, answer, state.facts)
    try:
        raw = one_shot(
            prompt, allowed_tools=[], model=model, json_schema=FACT_EXTRACTION_SCHEMA
        )
        data = json.loads(raw)
    except Exception:
        return {}
    facts = data.get("facts", {})
    if not isinstance(facts, dict):
        return {}
    return {
        key: value
        for key, value in facts.items()
        if isinstance(key, str) and isinstance(value, str) and value.strip()
    }


def apply_new_facts(
    state: ProjectState, role_id: str, new_facts: dict[str, str]
) -> ProjectState:
    for key, value in new_facts.items():
        state.facts[key] = value
        state.fact_sources[key] = role_id
    return state


def render_state_snapshot(state: ProjectState) -> str:
    if not state.facts:
        return "(brak ustalonych jeszcze faktów — to początek wywiadu)"
    return "\n".join(f"- {key}: {value}" for key, value in state.facts.items())
