"""Wspólne narzędzia tekstowe (slugify z transliteracją polskich znaków)."""

from __future__ import annotations

_PL_TRANSLIT = str.maketrans(
    "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ",
    "acelnoszzACELNOSZZ",
)


def slugify(text: str, *, max_length: int = 60, fallback: str = "item") -> str:
    ascii_text = text.translate(_PL_TRANSLIT)
    slug = "-".join(ascii_text.lower().split())
    slug = "".join(ch for ch in slug if ch.isalnum() or ch == "-")
    return slug[:max_length].strip("-") or fallback
