"""Moduł 3: Agentic Routing — Orchestrator ocenia skalę projektu i dopasowuje zakres
pytań kolejnych etapów (obecnie: QA/DevOps/UX) do tej skali.

Uruchamiany raz, po zakończeniu etapów Product Manager i Architekt (mają one
wystarczający kontekst biznesowo-techniczny), zanim ruszy etap QA/DevOps/UX.
"""

from __future__ import annotations

import json

from claude_planner.claude_client import one_shot
from claude_planner.models import ProjectScale

SCALE_SCHEMA = {
    "type": "object",
    "properties": {
        "scale": {"type": "string", "enum": [s.value for s in ProjectScale]},
        "justification": {"type": "string"},
    },
    "required": ["scale", "justification"],
}

ORCHESTRATOR_SYSTEM_PROMPT = """Jesteś Orchestratorem oceniającym skalę projektu IT na
podstawie ustaleń wywiadu discovery (etapy Product Manager i Architekt).

Kategorie skali (wybierz DOKŁADNIE jedną):
- Micro: strona wizytówkowa / prosty skrypt / jeden deweloper, brak zespołu, wystarczy
  hosting współdzielony, brak potrzeby CI/CD ani konteneryzacji.
- Small: prosta aplikacja webowa dla jednego klienta, mały zespół (1-3 osoby), jedno
  środowisko produkcyjne, podstawowy deploy wystarczy.
- Medium: aplikacja z realnym ruchem/kilkoma integracjami, zespół kilkuosobowy,
  potrzebne środowiska dev/staging/prod, sensowne jest CI/CD i podstawowy monitoring.
- Enterprise: wysoka dostępność/skala, wymagania compliance, wiele zespołów/serwisów,
  potrzebna pełna platforma: konteneryzacja, orkiestracja, obserwowalność, WCAG/a11y,
  formalne SLA.

Oceniaj WYŁĄCZNIE na podstawie dostarczonych ustaleń — nie zgaduj i nie zakładaj
"enterprise na wszelki wypadek". Brak wzmianki o skali ruchu/zespole/budżecie to
sygnał NISKIEJ skali, nie wysokiej. Zwróć WYŁĄCZNIE JSON zgodny ze schematem: skalę
oraz krótkie (1-2 zdania) uzasadnienie po polsku."""


def assess_project_scale(
    context_block: str, *, model: str | None = None
) -> tuple[ProjectScale, str]:
    """Zwraca ocenioną skalę + uzasadnienie. Bezpieczny fallback na `Small`, jeśli
    ocena się nie powiedzie — lepiej zapytać trochę za dużo niż całkowicie ubezwłasnowolnić
    kolejny etap wywiadu brakiem oceny."""
    try:
        raw = one_shot(
            context_block,
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            allowed_tools=[],
            model=model,
            json_schema=SCALE_SCHEMA,
        )
        data = json.loads(raw)
        return ProjectScale(data["scale"]), data.get("justification", "")
    except Exception:
        return (
            ProjectScale.SMALL,
            "(nie udało się ocenić skali automatycznie — domyślnie Small)",
        )


QA_SCALE_INSTRUCTIONS: dict[ProjectScale, str] = {
    ProjectScale.MICRO: (
        "Skala projektu to: Micro. Zignoruj pytania o architekturę chmurową, "
        "konteneryzację, CI/CD i WCAG. Skup się WYŁĄCZNIE na podstawowym wdrożeniu, "
        "zabezpieczeniu prostego hostingu i minimalnym ręcznym sprawdzeniu przed "
        "publikacją."
    ),
    ProjectScale.SMALL: (
        "Skala projektu to: Small. Pomiń pytania o wieloregionową skalowalność, "
        "konteneryzację/k8s i formalne SLA. Skup się na podstawowym CI (build + test), "
        "jednym środowisku staging i prostym monitoringu błędów."
    ),
    ProjectScale.MEDIUM: (
        "Skala projektu to: Medium. Pytaj o CI/CD, środowiska dev/staging/prod, "
        "podstawowy monitoring i logowanie. Pomiń pytania o compliance na poziomie "
        "enterprise i wieloregionową wysoką dostępność, chyba że klient sam je poruszy."
    ),
    ProjectScale.ENTERPRISE: (
        "Skala projektu to: Enterprise. Dopytaj o pełny pipeline CI/CD, "
        "konteneryzację/orkiestrację, obserwowalność (logi/metryki/tracing), WCAG/a11y "
        "i wymagania compliance/SLA."
    ),
}


def qa_scale_instruction(scale: ProjectScale | None) -> str:
    if scale is None:
        return ""
    return QA_SCALE_INSTRUCTIONS[scale]
