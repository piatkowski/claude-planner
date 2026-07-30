"""Wspólne środowisko Jinja2 dla szablonów strukturalnych (agenci, komendy, ADR, CLAUDE.md)."""

from __future__ import annotations

from jinja2 import Environment, PackageLoader, select_autoescape

_env: Environment | None = None


def get_env() -> Environment:
    global _env
    if _env is None:
        _env = Environment(
            loader=PackageLoader("claude_planner", "templates"),
            autoescape=select_autoescape(disabled_extensions=(".j2",), default=False),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _env


def render(template_name: str, **context) -> str:
    return get_env().get_template(template_name).render(**context)
