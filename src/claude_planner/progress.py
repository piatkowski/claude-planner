"""Wspólny spinner na czas blokujących wywołań `claude -p`.

`ClaudeSession.send`/`one_shot` (zob. `claude_client.py`) blokują na
`subprocess.run` bez żadnego postępu — pojedyncze wywołanie potrafi trwać
nawet kilka minut. Bez wizualnej oznaki w tym czasie użytkownik nie ma jak
odróżnić "Claude myśli" od "narzędzie się zawiesiło".
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from rich.console import Console


@contextmanager
def thinking(console: Console, message: str) -> Iterator[None]:
    with console.status(f"{message} (może to potrwać kilka minut)...", spinner="dots"):
        yield
