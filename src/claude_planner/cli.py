"""CLI `claude-planner` (Typer)."""

from __future__ import annotations

import enum
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from claude_planner import __version__
from claude_planner.claude_client import ClaudeCLIError, ClaudeNotFoundError, ensure_claude_available
from claude_planner.generator import generate_environment
from claude_planner.intake import IntakeError
from claude_planner.models import ProjectBrief
from claude_planner.profile_generator import generate_profile, profile_to_yaml
from claude_planner.profiles import DEFAULT_CUSTOM_PROFILES_DIR, get_profile, load_all_profiles
from claude_planner.scaffold import ScaffoldError, run_init
from claude_planner.textutils import slugify

app = typer.Typer(
    name="claude-planner",
    help="Generator żywego środowiska Claude Code do planowania projektów IT.",
    no_args_is_help=True,
)
profiles_app = typer.Typer(help="Przeglądanie i tworzenie profili stacków.")
app.add_typer(profiles_app, name="profiles")

console = Console()


class ModelChoice(str, enum.Enum):
    sonnet = "sonnet"
    opus = "opus"


PROFILES_DIR_OPTION = typer.Option(
    None,
    "--profiles-dir",
    help=f"Katalog z własnymi profilami (oprócz wbudowanych). Domyślnie: {DEFAULT_CUSTOM_PROFILES_DIR}",
)


def _resolve_profiles_dir(profiles_dir: Path | None) -> Path:
    return profiles_dir or DEFAULT_CUSTOM_PROFILES_DIR


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
def profiles_list(profiles_dir: Path = PROFILES_DIR_OPTION) -> None:
    """Wypisz dostępne profile stacków (wbudowane + własne)."""
    profiles = load_all_profiles(extra_dir=_resolve_profiles_dir(profiles_dir))
    table = Table(title="Profile stacków")
    table.add_column("ID", style="cyan")
    table.add_column("Nazwa")
    table.add_column("Języki/Frameworki")
    for profile in sorted(profiles.values(), key=lambda p: p.id):
        techs = ", ".join(profile.languages + profile.frameworks)
        table.add_row(profile.id, profile.name, techs)
    console.print(table)


@profiles_app.command("show")
def profiles_show(profile_id: str, profiles_dir: Path = PROFILES_DIR_OPTION) -> None:
    """Pokaż szczegóły jednego profilu."""
    profiles = load_all_profiles(extra_dir=_resolve_profiles_dir(profiles_dir))
    profile = profiles.get(profile_id)
    if not profile:
        console.print(f"[red]Nieznany profil: {profile_id}[/red]")
        raise typer.Exit(code=1)
    console.print(profile.model_dump())


@profiles_app.command("create")
def profiles_create(
    stack_description: str = typer.Argument(
        ..., help='Opis stacku, np. "Ruby on Rails + Sidekiq + PostgreSQL".'
    ),
    profile_id: str = typer.Option(
        None, "--id", help="ID profilu (kebab-case); domyślnie wyprowadzone z opisu."
    ),
    profiles_dir: Path = PROFILES_DIR_OPTION,
    model: ModelChoice = typer.Option(
        None, "--model", help="Model Claude do wygenerowania profilu (sonnet/opus)."
    ),
    force: bool = typer.Option(False, "--force", help="Nadpisz profil, jeśli już istnieje."),
) -> None:
    """Wygeneruj nowy profil stacku przy pomocy Claude i zapisz go jako YAML."""
    try:
        ensure_claude_available()
    except ClaudeNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    resolved_id = profile_id or slugify(stack_description, fallback="nowy-profil")
    target_dir = _resolve_profiles_dir(profiles_dir)
    target_path = target_dir / f"{resolved_id}.yaml"

    if target_path.exists() and not force:
        if not Confirm.ask(f"Profil '{resolved_id}' już istnieje w {target_path}. Nadpisać?", default=False):
            raise typer.Exit()

    chosen_model = model or ModelChoice(Prompt.ask("Model Claude", choices=["sonnet", "opus"], default="sonnet"))

    console.print(f"Generuję profil '{resolved_id}' dla stacku: {stack_description} (model: {chosen_model.value})...")
    try:
        profile = generate_profile(stack_description, resolved_id, model=chosen_model.value)
    except ClaudeCLIError as exc:
        console.print(f"[red]Błąd generowania profilu: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    target_dir.mkdir(parents=True, exist_ok=True)
    target_path.write_text(profile_to_yaml(profile), encoding="utf-8")

    console.rule("[bold green]Gotowe")
    console.print(f"Zapisano profil: {target_path}")
    console.print(f"Użyj go przez: claude-planner init --profile {resolved_id} --profiles-dir {target_dir}")


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
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    profile: list[str] = typer.Option(
        None, "--profile", "-p", help="ID profilu technologicznego (można podać kilka razy)."
    ),
    profiles_dir: Path = PROFILES_DIR_OPTION,
    model: ModelChoice = typer.Option(
        None, "--model", help="Model Claude do użycia w wywiadzie i generowaniu (sonnet/opus)."
    ),
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

    resolved_profiles_dir = _resolve_profiles_dir(profiles_dir)
    profile_ids = list(profile) if profile else []
    if not profile_ids:
        available = load_all_profiles(extra_dir=resolved_profiles_dir)
        profile_ids = _select_profiles(list(available.keys()))

    if model is None:
        model = ModelChoice(Prompt.ask("Model Claude", choices=["sonnet", "opus"], default="sonnet"))

    console.print(
        f"\n[bold]Projekt:[/bold] {project_name}  [bold]Klient:[/bold] {client_name}\n"
        f"[bold]Output:[/bold] {output}  [bold]Profile:[/bold] {', '.join(profile_ids)}\n"
        f"[bold]Intake:[/bold] {intake or '(brak)'}  [bold]Model:[/bold] {model.value}\n"
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
            model=model.value,
            console=console,
            profiles_dir=resolved_profiles_dir,
        )
    except (ScaffoldError, ClaudeCLIError, IntakeError, KeyError) as exc:
        console.print(f"[red]Błąd: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.rule("[bold green]Gotowe")
    console.print(f"Środowisko wygenerowane w: {output}")
    console.print(f"Dokumenty: {', '.join(summary['docs'])}")
    console.print(f"ADR: {summary['adr_count']}")
    console.print(f"Agenci: {', '.join(summary['agents'])}")
    console.print(f"Komendy: {', '.join('/' + c for c in summary['commands'])}")


@app.command()
def regenerate(
    output: Path = typer.Argument(
        ...,
        help="Katalog projektu wygenerowanego wcześniej przez `init` (musi zawierać .planner/brief.json).",
    ),
    profiles_dir: Path = PROFILES_DIR_OPTION,
    model: ModelChoice = typer.Option(
        None, "--model", help="Model Claude do użycia (sonnet/opus)."
    ),
) -> None:
    """Odtwórz docs/ i .claude/ z zapisanego briefu, bez powtarzania wywiadu discovery.

    Przydatne, gdy `init` przeprowadził wywiad, ale generowanie środowiska nie powiodło
    się (np. timeout/rate limit Claude) — brief jest zawsze zapisywany na dysk przed
    generowaniem, więc nic z rozmowy z klientem nie przepada.
    """
    try:
        ensure_claude_available()
    except ClaudeNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    brief_path = output / ".planner" / "brief.json"
    if not brief_path.exists():
        console.print(
            f"[red]Nie znaleziono {brief_path} — ten katalog nie wygląda na projekt "
            "claude-planner z zapisanym briefem.[/red]"
        )
        raise typer.Exit(code=1)

    brief = ProjectBrief.model_validate_json(brief_path.read_text(encoding="utf-8"))
    resolved_profiles_dir = _resolve_profiles_dir(profiles_dir)
    try:
        profiles = [get_profile(pid, extra_dir=resolved_profiles_dir) for pid in brief.profile_ids]
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(
        f"Regeneruję środowisko w {output} z zapisanego briefu "
        f"(profile: {', '.join(brief.profile_ids)})..."
    )
    try:
        summary = generate_environment(brief, profiles, output, model=model.value if model else None)
    except ClaudeCLIError as exc:
        console.print(f"[red]Błąd: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.rule("[bold green]Gotowe")
    console.print(f"Środowisko zregenerowane w: {output}")
    console.print(f"Dokumenty: {', '.join(summary['docs'])}")
    console.print(f"ADR: {summary['adr_count']}")


if __name__ == "__main__":
    app()
