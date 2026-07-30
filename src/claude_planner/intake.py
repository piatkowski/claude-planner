"""Analiza folderu z materiałami od klienta (spec, MVP, makiety, schemat bazy itd.)."""

from __future__ import annotations

from pathlib import Path

from claude_planner.claude_client import READ_ONLY_TOOLS, one_shot

SUMMARY_PROMPT = """W folderze, do którego masz dostęp przez Read/Glob/Grep, znajdują się
materiały od klienta dotyczące nowego projektu IT (mogą to być: notatki tekstowe,
wstępna specyfikacja, opis MVP, makiety HTML, schemat bazy danych, dowolne inne pliki).

Przejrzyj zawartość tego folderu (zacznij od Glob "**/*", potem Read najważniejszych
plików) i napisz zwięzłe, rzeczowe streszczenie po polsku, w punktach, obejmujące:
- co wynika z materiałów o celu/zakresie produktu,
- jakie technologie/rozwiązania są już zasugerowane lub narzucone,
- jakie dane/encje widać w schemacie bazy (jeśli jest),
- jakie kluczowe ekrany/flow widać w makietach (jeśli są),
- co jest niejasne lub czego brakuje w materiałach (do dopytania w wywiadzie).

Zwróć WYŁĄCZNIE treść streszczenia w Markdown, bez dodatkowych komentarzy typu
"oto streszczenie".
"""


def summarize_intake(intake_path: str | Path | None, *, model: str | None = None) -> str:
    if not intake_path:
        return "(brak folderu z materiałami od klienta — nic do analizy)"
    path = Path(intake_path)
    if not path.is_dir() or not any(path.iterdir()):
        return "(folder z materiałami od klienta jest pusty)"

    return one_shot(
        SUMMARY_PROMPT,
        add_dirs=[str(path)],
        allowed_tools=READ_ONLY_TOOLS,
        model=model,
    )
