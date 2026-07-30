# claude-planner

Generator kompletnego, **żywego** środowiska Claude Code do planowania projektów IT
dla software house'u — dla dowolnego stacku technologicznego.

`claude-planner init` tworzy nowe, lokalne repo projektu i wypełnia je:

- **wywiadem discovery** prowadzonym sekwencyjnie przez cztery role software house'u
  (Product Manager/BA → Architekt/Tech Lead → Backend/Frontend Developer → QA/DevOps/UX),
  zaimplementowanym jako seria non-interactive sesji `claude -p`,
- **analizą materiałów od klienta** (spec, notatki, makiety HTML, schemat bazy danych —
  dowolny folder podany przez `--intake`), którą Claude wykonuje sam, narzędziami
  Read/Glob/Grep,
- **kompletną dokumentacją planistyczną** w `docs/`: wizja produktu, backlog/PRD,
  roadmapa, standardy kodowania, Definition of Done, strategia testów, ADR-y,
- **środowiskiem Claude Code** w `.claude/`: agenci (role software house'u + agenci
  specyficzni dla wybranego stacku), skille, custom slash commands
  (`/new-adr`, `/update-roadmap`, `/update-state`, `/log-decision`, `/daily-standup`,
  `/sprint-review`), minimalne hooki,
- **plikiem `state.md`** — jedynym źródłem prawdy o bieżącym stanie projektu,
  aktualizowanym WYŁĄCZNIE przez `/update-state` (nadpisywany w całości, żeby nie
  puchł z czasem).

Narzędzie generuje **tylko artefakty planistyczne** — nie tworzy szkieletu kodu
aplikacji. Kod pisze się później, już z pomocą wygenerowanego środowiska.

## Instalacja

```bash
pipx install claude-planner   # docelowo, po publikacji na PyPI
# albo lokalnie z tego repo:
uv pip install -e .
```

Wymaga zainstalowanego [Claude Code CLI](https://docs.claude.com/claude-code)
(`claude` w PATH) — sprawdź przez `claude-planner doctor`.

## Użycie

```bash
claude-planner profiles list
claude-planner init \
  --name "Sklep XYZ" \
  --client "Acme Sp. z o.o." \
  --output ./sklep-xyz \
  --intake ~/software-house/clients/acme/sklep-xyz/intake \
  --profile web-fullstack --profile postgresql-pgvector-postgis
```

Bez flag `init` zapyta interaktywnie o wszystko, co potrzebne (nazwa, klient,
ścieżka wyjściowa, folder z materiałami, profile).

## Profile stacków

Profile to deklaratywne pliki YAML w `src/claude_planner/profiles/*.yaml` — każdy
opisuje języki/frameworki, dodatkowych agentów, skille i wskazówki dla Claude
przy generowaniu standardów kodowania/testów. Profile są **składalne**: projekt
może użyć kilku naraz (np. `web-fullstack` + `postgresql-pgvector-postgis` + `ai-ml`).

Dostępne w v1: `web-fullstack`, `backend-api`, `mobile`, `python`,
`wordpress-woocommerce`, `ai-ml`, `postgresql-pgvector-postgis`, `generic` (fallback).

Dodanie nowego profilu = nowy plik YAML w `profiles/`, zero zmian w kodzie Pythona.
Schemat pól: zobacz `src/claude_planner/models.py::StackProfile`.

## Architektura

```
src/claude_planner/
  cli.py            — CLI (Typer): init, profiles list/show, doctor
  claude_client.py  — wrapper na `claude -p` (non-interactive, --session-id/--resume)
  interview.py      — sekwencyjny wywiad per rola, wymuszony JSON (--json-schema)
  intake.py         — analiza folderu z materiałami od klienta
  generator.py      — generowanie docs/ i .claude/ (Claude dla treści merytorycznej,
                       Jinja2 dla struktury: frontmatter agentów/komend/skilli)
  scaffold.py        — orkiestracja `init`: git init, metadane, commit startowy
  roles.py          — 4 bazowe role software house'u jako agenci Claude Code
  profiles/          — deklaratywne profile stacków (YAML)
  templates/         — szablony Jinja2 (CLAUDE.md, agent.j2, skill.j2, komendy, ADR)
```

Claude jest wywoływany wyłącznie z narzędziami tylko-do-odczytu (Read/Glob/Grep)
podczas wywiadu i generowania — zapis plików na dysku wykonuje Python
deterministycznie, po otrzymaniu treści od Claude.

## Rozwój

```bash
uv pip install -e ".[dev]"
pytest
```
