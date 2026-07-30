"""CLI `claude-planner` (Typer)."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from claude_planner import __version__
from claude_planner.claude_client import ClaudeCLIError, ClaudeNotFoundError, ensure_claude_available
from claude_planner.profiles import load_all_profiles
from claude_planner.scaffold import ScaffoldError, run_init

app = typer.Typer(
    name="claude-planner",
    help="Generator żywego środowiska Claude Code do planowania projektów IT.",
    no_args_is_help=True,
)
profiles_app = typer.Typer(help="Przeglądanie dostępnych profili stacków.")
app.add_typer(profiles_app, name="profiles")

console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"claude-planner {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Pokaż wersję i zakończ."
    ),
) -> None:
    pass


@app.command()
def doctor() -> None:
    """Sprawdź, czy środowisko (Claude Code CLI) jest gotowe do pracy."""
    try:
        path = ensure_claude_available()
        console.print(f"[green]OK[/green] `claude` znaleziony: {path}")
    except ClaudeNotFoundError as exc:
        console.print(f"[red]BŁĄD[/red] {exc}")
        raise typer.Exit(code=1) from exc


@profiles_app.command("list")
def profiles_list() -> None:
    """Wypisz dostępne profile stacków."""
    profiles = load_all_profiles()
    table = Table(title="Profile stacków")
    table.add_column("ID", style="cyan")
    table.add_column("Nazwa")
    table.add_column("Języki/Frameworki")
    for profile in sorted(profiles.values(), key=lambda p: p.id):
        techs = ", ".join(profile.languages + profile.frameworks)
        table.add_row(profile.id, profile.name, techs)
    console.print(table)


@profiles_app.command("show")
def profiles_show(profile_id: str) -> None:
    """Pokaż szczegóły jednego profilu."""
    profiles = load_all_profiles()
    profile = profiles.get(profile_id)
    if not profile:
        console.print(f"[red]Nieznany profil: {profile_id}[/red]")
        raise typer.Exit(code=1)
    console.print(profile.model_dump())


def _select_profiles(available_ids: list[str]) -> list[str]:
    console.print("Dostępne profile: " + ", ".join(sorted(available_ids)))
    raw = Prompt.ask(
        "Wybierz profile technologiczne (rozdziel przecinkiem, można kilka)"
    )
    selected = [item.strip() for item in raw.split(",") if item.strip()]
    return selected


@app.command()
def init(
    project_name: str = typer.Option(None, "--name", help="Nazwa projektu."),
    client_name: str = typer.Option(None, "--client", help="Nazwa klienta."),
    output: Path = typer.Option(
        None, "--output", "-o", help="Ścieżka, w której zostanie utworzone nowe repo projektu."
    ),
    intake: Path = typer.Option(
        None,
        "--intake",
        help="Ścieżka do folderu z materiałami od klienta (spec, MVP, makiety, schemat DB itd.).",
    ),
    profile: list[str] = typer.Option(
        None, "--profile", "-p", help="ID profilu technologicznego (można podać kilka razy)."
    ),
    model: str = typer.Option(None, "--model", help="Model Claude do użycia (opcjonalnie)."),
) -> None:
    """Utwórz nowe repo projektu i wygeneruj kompletne środowisko planistyczne."""
    try:
        ensure_claude_available()
    except ClaudeNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    project_name = project_name or Prompt.ask("Nazwa projektu")
    client_name = client_name or Prompt.ask("Nazwa klienta")
    output = output or Path(Prompt.ask("Ścieżka wyjściowa (nowe repo)", default=f"./{project_name}"))

    if intake is None:
        intake_raw = Prompt.ask(
            "Ścieżka do folderu z materiałami od klienta (Enter, jeśli brak)", default=""
        )
        intake = Path(intake_raw) if intake_raw.strip() else None

    profile_ids = list(profile) if profile else []
    if not profile_ids:
        available = load_all_profiles()
        profile_ids = _select_profiles(list(available.keys()))

    console.print(
        f"\n[bold]Projekt:[/bold] {project_name}  [bold]Klient:[/bold] {client_name}\n"
        f"[bold]Output:[/bold] {output}  [bold]Profile:[/bold] {', '.join(profile_ids)}\n"
        f"[bold]Intake:[/bold] {intake or '(brak)'}\n"
    )
    if not Confirm.ask("Rozpocząć wywiad i generowanie środowiska?", default=True):
        raise typer.Exit()

    try:
        summary = run_init(
            project_name=project_name,
            client_name=client_name,
            profile_ids=profile_ids,
            output_dir=output,
            intake_path=str(intake) if intake else None,
            model=model,
            console=console,
        )
    except (ScaffoldError, ClaudeCLIError, KeyError) as exc:
        console.print(f"[red]Błąd: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.rule("[bold green]Gotowe")
    console.print(f"Środowisko wygenerowane w: {output}")
    console.print(f"Dokumenty: {', '.join(summary['docs'])}")
    console.print(f"ADR: {summary['adr_count']}")
    console.print(f"Agenci: {', '.join(summary['agents'])}")
    console.print(f"Komendy: {', '.join('/' + c for c in summary['commands'])}")


if __name__ == "__main__":
    app()
