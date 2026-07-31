# claude-planner

Generator środowiska Claude Code do planowania projektów IT — dla dowolnego stacku.

`claude-planner init` tworzy lokalne repo projektu i wypełnia je:

- **wywiadem discovery** — sekwencja non-interactive sesji `claude -p`, cztery role
  software house'u (PM/BA → Architekt → Backend/Frontend Dev → QA/DevOps/UX),
- **analizą materiałów od klienta** (folder podany przez `--intake`: spec, notatki,
  makiety, schemat bazy) — Claude czyta go sam narzędziami Read/Glob/Grep,
- **dokumentacją planistyczną** w `docs/`: wizja, backlog/PRD, roadmapa, standardy
  kodowania, Definition of Done, strategia testów, ADR-y,
- **środowiskiem Claude Code** w `.claude/`: agenci, skille, slash commands
  (`/new-adr`, `/update-roadmap`, `/update-state`, `/log-decision`, `/daily-standup`,
  `/sprint-review`), hooki,
- **`state.md`** — jedyne źródło prawdy o stanie projektu, nadpisywane w całości przez
  `/update-state`,
- **`/setup-dev-environment`** — instaluje zależności/SDK wybranego stacku, wymagane
  dla LSP,
- **hookiem antyhalucynacyjnym** (`check-pinned-dependency.py`) — blokuje instalację
  pakietu z wersją "na sztywno", dopóki Claude nie sprawdzi jej realnie lub nie zapyta
  użytkownika,
- **`WORKFLOW.md`** wygenerowanym w projekcie — instrukcja "jak pracować z Claude Code
  w TYM projekcie", dopasowana do wybranych profili (przykład: [`WORKFLOW.md`](./WORKFLOW.md)).

Narzędzie generuje tylko artefakty planistyczne, nie szkielet kodu aplikacji.

## Instalacja

```bash
pipx install claude-planner   # docelowo, po publikacji na PyPI
# albo lokalnie z tego repo:
uv pip install -e .
```

Wymaga [Claude Code CLI](https://docs.claude.com/claude-code) (`claude` w PATH) —
sprawdź przez `claude-planner doctor`.

## Użycie

```bash
claude-planner profiles list
claude-planner init \
  --name "Sklep XYZ" \
  --client "Acme Sp. z o.o." \
  --output ./sklep-xyz \
  --intake ~/software-house/clients/acme/sklep-xyz/intake \
  --profile web-fullstack --profile postgresql-pgvector-postgis \
  --model sonnet   # albo opus — dobierany raz dla całego wywiadu+generowania
```

Bez flag `init` pyta interaktywnie o wszystko. Pełny przykład od `init` po wdrożenie:
[`WORKFLOW.md`](./WORKFLOW.md).

## Generowanie nowych profili przez Claude

Gdy żaden wbudowany profil nie pasuje do stacku, Claude projektuje nowy zamiast
ręcznego YAML-a:

```bash
claude-planner profiles create "Ruby on Rails + Sidekiq + PostgreSQL" \
  --id ruby-on-rails --model sonnet
```

Profil trafia do `~/.claude-planner/profiles/` (zmienne przez `--profiles-dir`) i jest
od razu widoczny w `profiles list`/`profiles show`/`init`.

## Profile stacków

Deklaratywne YAML w `src/claude_planner/profiles/*.yaml`, każdy opisuje
języki/frameworki, dodatkowych agentów, skille i wskazówki do standardów kodowania/testów.
Składalne — projekt może użyć kilku naraz (np. `web-fullstack` + `postgresql-pgvector-postgis`).

Dostępne w v1: `web-fullstack`, `backend-api`, `mobile`, `python`,
`wordpress-woocommerce`, `ai-ml`, `postgresql-pgvector-postgis`, `generic` (fallback),
`symfony`, `laravel`, `django`, `react-native`, `flutter`, `rag-ai-agents`,
`data-engineering`, `machine-learning`.

Nowy profil = nowy plik YAML w `profiles/`, zero zmian w kodzie Pythona. Schemat pól:
`src/claude_planner/models.py::StackProfile`.

## Architektura

```
src/claude_planner/
  cli.py               — CLI (Typer): init, profiles list/show/create, doctor
  claude_client.py     — wrapper na `claude -p` (--session-id/--resume)
  interview.py         — sekwencyjny wywiad per rola, wymuszony JSON (--json-schema)
  intake.py            — analiza folderu z materiałami od klienta
  generator.py         — generowanie docs/, .claude/, WORKFLOW.md (Claude dla treści,
                          Jinja2 dla struktury)
  profile_generator.py — generowanie nowego profilu stacku przez Claude
  scaffold.py           — orkiestracja `init`: git init, metadane, commit startowy
  roles.py              — 4 bazowe role software house'u jako agenci Claude Code
  textutils.py          — wspólne narzędzia (slugify z transliteracją PL)
  profiles/              — profile stacków (YAML); `DEFAULT_CUSTOM_PROFILES_DIR`
                          (`~/.claude-planner/profiles/`) dla profili od Claude
  templates/             — szablony Jinja2 (CLAUDE.md, WORKFLOW.md, agent.j2, skill.j2,
                          komendy, ADR, hook antyhalucynacyjny)
```

Claude jest wywoływany wyłącznie narzędziami do odczytu (Read/Glob/Grep) — zapis
plików wykonuje Python deterministycznie, po otrzymaniu treści od Claude.

## Rozwój

```bash
uv pip install -e ".[dev]"
pytest
```
