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
  puchł z czasem),
- **wymuszonym LSP/toolchainem**: komenda `/setup-dev-environment` instaluje
  zależności/SDK wybranego stacku — bez tego Claude Code nie ma z czego uruchomić
  code intelligence (LSP) dla projektu,
- **hookiem chroniącym przed halucynacją wersji zależności**: `PreToolUse` hook
  (`.claude/hooks/check-pinned-dependency.py`) blokuje komendy instalujące pakiet
  z "na sztywno" wpisaną wersją — Claude musi albo pominąć przypięcie, albo
  sprawdzić realną wersję komendą menedżera pakietów, albo zapytać użytkownika,
- **plikiem `WORKFLOW.md`** wygenerowanym w projekcie — konkretna instrukcja "jak
  pracować z Claude Code w TYM projekcie od A do Z", z listą dokładnie tych
  agentów/skilli/komend, które powstały dla danego stacku (przykład pełnego
  przebiegu: zobacz [`WORKFLOW.md`](./WORKFLOW.md) w tym repo).

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
  --profile web-fullstack --profile postgresql-pgvector-postgis \
  --model sonnet   # albo opus — dobierany jeden raz dla całego wywiadu+generowania
```

Bez flag `init` zapyta interaktywnie o wszystko, co potrzebne (nazwa, klient,
ścieżka wyjściowa, folder z materiałami, profile, model).

Pełny przykład użycia od `init` po wdrożenie: zobacz [`WORKFLOW.md`](./WORKFLOW.md).

## Generowanie nowych profili przez Claude

Jeśli żaden z wbudowanych profili nie pasuje do stacku, Claude może sam
zaprojektować nowy — zamiast pisać YAML ręcznie:

```bash
claude-planner profiles create "Ruby on Rails + Sidekiq + PostgreSQL" \
  --id ruby-on-rails --model sonnet
```

Profil trafia domyślnie do `~/.claude-planner/profiles/` (zmienne przez
`--profiles-dir`) i jest od razu widoczny w `profiles list`/`profiles show`/`init`
w tej samej lub innej sesji — bez zmian w kodzie narzędzia.

## Profile stacków

Profile to deklaratywne pliki YAML w `src/claude_planner/profiles/*.yaml` — każdy
opisuje języki/frameworki, dodatkowych agentów, skille i wskazówki dla Claude
przy generowaniu standardów kodowania/testów. Profile są **składalne**: projekt
może użyć kilku naraz (np. `web-fullstack` + `postgresql-pgvector-postgis` + `ai-ml`).

Dostępne w v1: `web-fullstack`, `backend-api`, `mobile`, `python`,
`wordpress-woocommerce`, `ai-ml`, `postgresql-pgvector-postgis`, `generic` (fallback),
`symfony`, `laravel`, `django`, `react-native`, `flutter`, `rag-ai-agents`,
`data-engineering`, `machine-learning`.

Dodanie nowego profilu = nowy plik YAML w `profiles/`, zero zmian w kodzie Pythona.
Schemat pól: zobacz `src/claude_planner/models.py::StackProfile`.

## Architektura

```
src/claude_planner/
  cli.py               — CLI (Typer): init, profiles list/show/create, doctor
  claude_client.py     — wrapper na `claude -p` (non-interactive, --session-id/--resume)
  interview.py         — sekwencyjny wywiad per rola, wymuszony JSON (--json-schema)
  intake.py            — analiza folderu z materiałami od klienta
  generator.py         — generowanie docs/, .claude/ i WORKFLOW.md (Claude dla treści
                          merytorycznej, Jinja2 dla struktury: agenci/komendy/skille/hooki)
  profile_generator.py — generowanie NOWEGO profilu stacku przez Claude (`profiles create`)
  scaffold.py           — orkiestracja `init`: git init, metadane, commit startowy
  roles.py             — 4 bazowe role software house'u jako agenci Claude Code
  textutils.py          — wspólne narzędzia (slugify z transliteracją PL)
  profiles/             — deklaratywne profile stacków (YAML); `DEFAULT_CUSTOM_PROFILES_DIR`
                          (`~/.claude-planner/profiles/`) dla profili wygenerowanych przez Claude
  templates/             — szablony Jinja2 (CLAUDE.md, WORKFLOW.md, agent.j2, skill.j2,
                          komendy, ADR, hook antyhalucynacyjny)
```

Claude jest wywoływany wyłącznie z narzędziami tylko-do-odczytu (Read/Glob/Grep)
podczas wywiadu i generowania — zapis plików na dysku wykonuje Python
deterministycznie, po otrzymaniu treści od Claude.

## Rozwój

```bash
uv pip install -e ".[dev]"
pytest
```
