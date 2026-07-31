"""Cienki wrapper na `claude` CLI w trybie non-interactive (-p / print mode).

Cała orkiestracja (wywiad, generowanie dokumentów) dzieje się z poziomu Pythona:
każde wywołanie `claude -p` to jeden krok, a wieloturowa rozmowa jest utrzymywana
przez `--session-id` / `--resume`, tak jak zaleca dokumentacja CLI dla skryptów.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from dataclasses import dataclass

DEFAULT_TIMEOUT_SECONDS = 300
READ_ONLY_TOOLS = ["Read", "Glob", "Grep"]


class ClaudeCLIError(RuntimeError):
    """Wywołanie `claude` zakończyło się błędem lub zwróciło nieoczekiwany format."""


class ClaudeNotFoundError(ClaudeCLIError):
    """Binarka `claude` nie jest dostępna w PATH."""


class ClaudeStructuredOutputError(ClaudeCLIError):
    """`claude` wyczerpał własne, wewnętrzne próby dopasowania odpowiedzi do
    `--json-schema` (`error_max_structured_output_retries`). To zwykle błąd
    przejściowy modelu, a nie problem z promptem/schematem — warto ponowić
    całe wywołanie."""


@dataclass
class ClaudeTurnResult:
    text: str
    session_id: str | None
    is_error: bool = False
    raw: dict | None = None


def ensure_claude_available() -> str:
    path = shutil.which("claude")
    if not path:
        raise ClaudeNotFoundError(
            "Nie znaleziono `claude` w PATH. Zainstaluj Claude Code CLI: "
            "https://docs.claude.com/claude-code"
        )
    return path


class ClaudeSession:
    """Jedna kontynuowana, non-interactive rozmowa z Claude (jedna rola/etap wywiadu)."""

    def __init__(
        self,
        *,
        system_prompt: str | None = None,
        add_dirs: list[str] | None = None,
        allowed_tools: list[str] | None = None,
        model: str | None = None,
        cwd: str | None = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        json_schema: dict | None = None,
    ) -> None:
        self.session_id = str(uuid.uuid4())
        self._turns = 0
        self.system_prompt = system_prompt
        self.add_dirs = add_dirs or []
        self.allowed_tools = READ_ONLY_TOOLS if allowed_tools is None else allowed_tools
        self.model = model
        self.cwd = cwd
        self.timeout = timeout
        self.json_schema = json_schema

    def _build_command(self, prompt: str) -> list[str]:
        cmd = ["claude", "-p", prompt, "--output-format", "json"]
        if self._turns == 0:
            cmd += ["--session-id", self.session_id]
            if self.system_prompt:
                cmd += ["--system-prompt", self.system_prompt]
        else:
            cmd += ["--resume", self.session_id]
        for directory in self.add_dirs:
            cmd += ["--add-dir", directory]
        # --tools faktycznie ogranicza zestaw narzędzi dostępnych dla modelu;
        # --allowedTools tylko auto-zatwierdza permission prompty dla tych narzędzi
        # (bez niego wywołania odczytowe czekałyby na akceptację w trybie non-interactive).
        cmd += ["--tools", ",".join(self.allowed_tools)]
        if self.allowed_tools:
            cmd += ["--allowedTools", " ".join(self.allowed_tools)]
        if self.model:
            cmd += ["--model", self.model]
        if self.json_schema:
            cmd += ["--json-schema", json.dumps(self.json_schema)]
        return cmd

    def send(self, prompt: str) -> ClaudeTurnResult:
        ensure_claude_available()
        cmd = self._build_command(prompt)
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.cwd,
            )
        except subprocess.TimeoutExpired as exc:
            raise ClaudeCLIError(
                f"`claude` nie odpowiedział w {self.timeout}s (rola/etap: {self.session_id})."
            ) from exc

        if proc.returncode != 0:
            try:
                parsed = json.loads(proc.stdout.strip())
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict) and parsed.get("subtype") == "error_max_structured_output_retries":
                errors = "; ".join(parsed.get("errors", [])) or "brak szczegółów"
                raise ClaudeStructuredOutputError(
                    "Claude nie zdołał wygenerować odpowiedzi zgodnej ze schematem JSON "
                    f"po własnych próbach ({errors})."
                )
            raise ClaudeCLIError(
                f"`claude` zakończył się kodem {proc.returncode}.\n"
                f"stderr:\n{proc.stderr}\nstdout:\n{proc.stdout}"
            )

        result = self._parse_output(proc.stdout, proc.stderr)
        self._turns += 1
        return result

    @staticmethod
    def _parse_output(stdout: str, stderr: str) -> ClaudeTurnResult:
        stdout = stdout.strip()
        if not stdout:
            raise ClaudeCLIError(f"Puste wyjście z `claude`. stderr:\n{stderr}")
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise ClaudeCLIError(
                f"Nie udało się sparsować JSON z `claude --output-format json`.\n"
                f"stdout:\n{stdout}\nstderr:\n{stderr}"
            ) from exc

        is_error = bool(data.get("is_error", False))
        text = data.get("result", "")
        session_id = data.get("session_id")
        if is_error:
            raise ClaudeCLIError(f"Claude zwrócił błąd: {text or data}")
        return ClaudeTurnResult(text=text, session_id=session_id, is_error=is_error, raw=data)


STRUCTURED_OUTPUT_MAX_RETRIES = 2


def one_shot(
    prompt: str,
    *,
    system_prompt: str | None = None,
    add_dirs: list[str] | None = None,
    allowed_tools: list[str] | None = None,
    model: str | None = None,
    cwd: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    json_schema: dict | None = None,
    max_retries: int = STRUCTURED_OUTPUT_MAX_RETRIES,
) -> str:
    """Pojedyncze, bezstanowe wywołanie — użyteczne do generowania jednego dokumentu.

    Przy `json_schema` porażka bywa przejściowa (model chwilowo nie trafia w
    schemat, `--json-schema` wewnętrznie wyczerpuje własne próby) — ponawiamy
    całe wywołanie `claude` od nowa, zamiast od razu wywalać cały krok generowania.
    """
    attempt = 0
    while True:
        session = ClaudeSession(
            system_prompt=system_prompt,
            add_dirs=add_dirs,
            allowed_tools=allowed_tools,
            model=model,
            cwd=cwd,
            timeout=timeout,
            json_schema=json_schema,
        )
        try:
            return session.send(prompt).text
        except ClaudeStructuredOutputError:
            if attempt >= max_retries:
                raise
            attempt += 1
