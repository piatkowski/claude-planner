"""Orkiestracja `init`: tworzy nowe lokalne repo projektu i generuje w nim środowisko."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

import yaml
from rich.console import Console

from claude_planner.claude_client import ClaudeCLIError
from claude_planner.generator import generate_environment
from claude_planner.intake import summarize_intake
from claude_planner.interview import InterviewRunner
from claude_planner.models import ProjectBrief
from claude_planner.profiles import get_profile
from claude_planner.roles import INTERVIEW_ROLES


class ScaffoldError(RuntimeError):
    """Błąd na etapie tworzenia/generowania projektu."""


def _git_init(output_dir: Path, console: Console) -> None:
    if (output_dir / ".git").exists():
        return
    try:
        subprocess.run(
            ["git", "init", "-q"], cwd=output_dir, check=True, capture_output=True, text=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        console.print(f"[yellow]Uwaga: nie udało się wykonać `git init` ({exc}).[/yellow]")


def _ensure_git_identity(output_dir: Path) -> None:
    """Ustawia lokalną (repo-only) tożsamość git, jeśli nie ma jej ani lokalnie, ani globalnie."""
    check = subprocess.run(
        ["git", "config", "user.email"], cwd=output_dir, capture_output=True, text=True
    )
    if check.returncode != 0 or not check.stdout.strip():
        subprocess.run(
            ["git", "config", "user.email", "planner@localhost"], cwd=output_dir, check=True
        )
        subprocess.run(["git", "config", "user.name", "claude-planner"], cwd=output_dir, check=True)


def _git_initial_commit(output_dir: Path, console: Console) -> None:
    try:
        _ensure_git_identity(output_dir)
        subprocess.run(
            ["git", "add", "-A"], cwd=output_dir, check=True, capture_output=True, text=True
        )
        subprocess.run(
            ["git", "commit", "-q", "-m", "chore: initial claude-planner environment"],
            cwd=output_dir,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        console.print(
            "[yellow]Uwaga: nie udało się utworzyć commita startowego "
            f"(sprawdź `git config user.name/user.email`): {exc}[/yellow]"
        )


def run_init(
    *,
    project_name: str,
    client_name: str,
    profile_ids: list[str],
    output_dir: Path,
    intake_path: str | None,
    model: str | None,
    console: Console,
    profiles_dir: Path | None = None,
) -> dict:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ScaffoldError(f"Katalog docelowy '{output_dir}' już istnieje i nie jest pusty.")
    if not profile_ids:
        raise ScaffoldError("Wybierz co najmniej jeden profil technologiczny (--profile).")

    try:
        profiles = [get_profile(pid, extra_dir=profiles_dir) for pid in profile_ids]
    except KeyError as exc:
        raise ScaffoldError(str(exc)) from exc
    output_dir.mkdir(parents=True, exist_ok=True)

    console.rule("[bold]Analiza materiałów od klienta")
    intake_summary = summarize_intake(intake_path, model=model)
    console.print(intake_summary)

    console.rule("[bold]Wywiad discovery")
    runner = InterviewRunner(
        project_name=project_name,
        client_name=client_name,
        profiles=profiles,
        intake_path=intake_path,
        model=model,
        console=console,
    )
    try:
        stages = runner.run(INTERVIEW_ROLES)
    except ClaudeCLIError:
        # Wywiad z klientem to godziny pracy człowieka — nawet jeśli padnie w połowie,
        # to co zdążyliśmy zebrać (runner.completed_stages) trafia na dysk, żeby nic
        # nie przepadło i żeby dało się to później dokończyć bez powtarzania wywiadu.
        console.print(
            "[red]Wywiad przerwany błędem Claude — zapisuję to, co już ustalono, "
            "zamiast to tracić.[/red]"
        )
        partial_brief = ProjectBrief(
            project_name=project_name,
            client_name=client_name,
            profile_ids=profile_ids,
            intake_path=str(intake_path) if intake_path else None,
            intake_summary=intake_summary,
            stages=runner.completed_stages,
        )
        _write_metadata(output_dir, partial_brief)
        raise

    brief = ProjectBrief(
        project_name=project_name,
        client_name=client_name,
        profile_ids=profile_ids,
        intake_path=str(intake_path) if intake_path else None,
        intake_summary=intake_summary,
        stages=stages,
    )

    # Brief zapisujemy PRZED generowaniem środowiska (a nie po) — jeśli generowanie
    # padnie (np. timeout/rate limit Claude w trakcie 7+ wywołań), wywiad discovery
    # nie zostaje bezpowrotnie utracony: `claude-planner regenerate` dokończy z briefu.
    _write_metadata(output_dir, brief)

    console.rule("[bold]Generowanie środowiska")
    try:
        summary = generate_environment(brief, profiles, output_dir, model=model)
    except ClaudeCLIError:
        console.print(
            "[red]Generowanie środowiska nie powiodło się. Brief i transkrypt wywiadu "
            f"są zapisane w {output_dir / '.planner'} — napraw przyczynę błędu i uruchom "
            "`claude-planner regenerate` na tym katalogu zamiast powtarzać wywiad.[/red]"
        )
        raise

    _git_init(output_dir, console)
    _git_initial_commit(output_dir, console)

    return summary


def _write_metadata(output_dir: Path, brief: ProjectBrief) -> None:
    meta_dir = output_dir / ".planner"
    meta_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "project_name": brief.project_name,
        "client_name": brief.client_name,
        "profile_ids": brief.profile_ids,
        "intake_path": brief.intake_path,
        "created_at": date.today().isoformat(),
        "language": brief.language,
    }
    (meta_dir / "project.yaml").write_text(
        yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    # Pełny brief w JSON (maszynowo odczytywalny) — pozwala `claude-planner regenerate`
    # odtworzyć środowisko bez ponownego przeprowadzania wywiadu z klientem.
    (meta_dir / "brief.json").write_text(brief.model_dump_json(indent=2), encoding="utf-8")

    lines = [f"# Transkrypt wywiadu — {brief.project_name}\n"]
    for stage in brief.stages:
        lines.append(f"\n## {stage.display_name}\n")
        for item in stage.qa:
            lines.append(f"**P:** {item.question}\n\n**O:** {item.answer}\n")
        lines.append(f"\n**Podsumowanie etapu:**\n\n{stage.summary}\n")
    (meta_dir / "interview-transcript.md").write_text("\n".join(lines), encoding="utf-8")
