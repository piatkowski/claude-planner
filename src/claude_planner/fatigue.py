"""Moduł 4: detekcja zmęczenia użytkownika (fatigue) i circuit breaker.

Prosta, szybka detekcja intencji "zbywam to pytanie" na regexach (bez dodatkowego
wywołania LLM — to musi zadziałać natychmiast, w pętli obsługi każdej odpowiedzi).
Po `FATIGUE_THRESHOLD` takich odpowiedziach w ramach CAŁEGO wywiadu (nie per-etap,
żeby zmęczenie z jednego etapu nie "resetowało się" na starcie kolejnego) włącza się
circuit breaker: agent ma obowiązek zaproponować pominięcie reszty etapu zamiast
dalej drążyć szczegóły.
"""

from __future__ import annotations

import re

FATIGUE_THRESHOLD = 3

_DISMISSIVE_PATTERNS = [
    r"pomi[nń]",
    r"nieistotne",
    r"nie\s+wiem",
    r"zostaw(?:\s+to)?",
    r"bez\s+znaczenia",
    r"nie\s+ma\s+znaczenia",
    r"jak\s+(?:chcesz|uwa[zż]asz)",
    r"cokolwiek",
    r"dowolnie",
    r"\bskip\b",
    r"nie\s*wa[zż]ne",
    r"oboj[ęe]tne",
]
_DISMISSIVE_RE = re.compile("|".join(_DISMISSIVE_PATTERNS), re.IGNORECASE)

_AFFIRMATIVE_RE = re.compile(
    r"^\s*(tak|tak[,.]?\s*pomi[nń]|zgadzam\s+si[ęe]|ok(?:ej)?|dawaj|jasne|pomi[nń])\b",
    re.IGNORECASE,
)


def is_dismissive(text: str) -> bool:
    """True, jeśli odpowiedź wygląda na zbywającą pytanie (nie wnosi treści)."""
    return bool(_DISMISSIVE_RE.search(text.strip()))


def is_affirmative(text: str) -> bool:
    """True, jeśli odpowiedź na pytanie ratunkowe potwierdza pominięcie etapu."""
    return bool(_AFFIRMATIVE_RE.match(text.strip()))


RESCUE_MESSAGE = (
    "Widzę, że wiele technicznych szczegółów nie jest na ten moment priorytetem. "
    "Czy chcesz pominąć resztę tego etapu i wygenerować podsumowanie na bazie tego, "
    "co już mamy?"
)


class FatigueTracker:
    """Liczy zbywające odpowiedzi w całym wywiadzie i wyzwala circuit breaker raz."""

    def __init__(self, threshold: int = FATIGUE_THRESHOLD) -> None:
        self.threshold = threshold
        self.count = 0
        self.breaker_tripped = False

    def record(self, answer: str) -> bool:
        """Rejestruje odpowiedź. Zwraca True dokładnie w momencie przekroczenia progu
        (żeby wywołujący zareagował raz, a nie przy każdej kolejnej zbywającej odpowiedzi)."""
        if not is_dismissive(answer):
            return False
        self.count += 1
        if self.count >= self.threshold and not self.breaker_tripped:
            self.breaker_tripped = True
            return True
        return False
