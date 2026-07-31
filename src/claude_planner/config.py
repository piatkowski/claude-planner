"""Plik konfiguracyjny `claude-planner.json` — domyślne wartości dla `init`.

Odpowiednik `package.json` dla `npm init`: pozwala raz zapisać argumenty
polecenia `init` (nazwę projektu, klienta, profile, model itd.) i uruchamiać
`claude-planner init` bez powtarzania flag za każdym razem. Wartości z pliku
są nadpisywane przez flagi CLI, jeśli te zostaną podane.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

DEFAULT_CONFIG_FILENAME = "claude-planner.json"


class ConfigError(RuntimeError):
    """Błąd wczytywania/walidacji pliku konfiguracyjnego."""


class ProjectConfig(BaseModel):
    """Schemat `claude-planner.json` — te same pola co opcje `claude-planner init`."""

    name: str | None = None
    client: str | None = None
    output: str | None = None
    intake: str | None = None
    profiles: list[str] = Field(default_factory=list)
    profiles_dir: str | None = None
    model: str | None = None

    model_config = {"extra": "forbid"}


def find_default_config(start_dir: Path | None = None) -> Path | None:
    """Szuka `claude-planner.json` w podanym katalogu (domyślnie: bieżący)."""
    candidate = (start_dir or Path.cwd()) / DEFAULT_CONFIG_FILENAME
    return candidate if candidate.exists() else None


def load_config(path: Path) -> ProjectConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Nieprawidłowy JSON w {path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Nie można odczytać {path}: {exc}") from exc

    try:
        return ProjectConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"Nieprawidłowa konfiguracja w {path}:\n{exc}") from exc
