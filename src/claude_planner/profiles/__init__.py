"""Ładowanie deklaratywnych profili stacków z plików YAML."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import yaml

from claude_planner.models import StackProfile

_PROFILES_DIR = resources.files("claude_planner.profiles")

DEFAULT_CUSTOM_PROFILES_DIR = Path.home() / ".claude-planner" / "profiles"


def _iter_profile_files():
    for entry in _PROFILES_DIR.iterdir():
        if entry.name.endswith((".yaml", ".yml")):
            yield entry


def load_all_profiles(extra_dir: Path | None = None) -> dict[str, StackProfile]:
    """Wczytuje wbudowane profile oraz opcjonalnie dodatkowe z `extra_dir` (np. profile klienta)."""
    profiles: dict[str, StackProfile] = {}
    for entry in _iter_profile_files():
        data = yaml.safe_load(entry.read_text(encoding="utf-8"))
        profile = StackProfile.model_validate(data)
        profiles[profile.id] = profile

    if extra_dir and extra_dir.is_dir():
        for path in sorted(extra_dir.glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            profile = StackProfile.model_validate(data)
            profiles[profile.id] = profile

    return profiles


def get_profile(profile_id: str, extra_dir: Path | None = None) -> StackProfile:
    profiles = load_all_profiles(extra_dir=extra_dir)
    try:
        return profiles[profile_id]
    except KeyError as exc:
        available = ", ".join(sorted(profiles)) or "(brak)"
        raise KeyError(
            f"Nieznany profil '{profile_id}'. Dostępne: {available}"
        ) from exc
