# Workflow: `claude-planner` + Claude Code od `init` do wdrożenia

Konkretny przykład użycia `claude-planner` z Claude Code — od `init` po wdrożenie.
Narracja krok po kroku; referencja API jest w `README.md`.

> Po `init` każdy wygenerowany projekt dostaje **własny** `WORKFLOW.md`, dopasowany do
> wybranych profili i wygenerowanych agentów/skilli/komend. Ten plik to przykład dla
> całego narzędzia — tamten to instrukcja dla zespołu pracującego nad projektem klienta.

Przykład: software house robi sklep internetowy ("Sklep XYZ") dla klienta
"Acme Sp. z o.o." — web fullstack + PostgreSQL z pgvector (rekomendacje produktów).

## 0. Instalacja

```bash
pipx install claude-planner   # albo: uv pip install -e . w tym repo
claude-planner doctor         # sprawdza dostępność `claude` (Claude Code CLI)
```

## 1. Materiały od klienta (intake)

Trzymane poza repo projektu, np.:

```
~/software-house/clients/acme/sklep-xyz/intake/
  ├── brief.txt
  ├── specyfikacja-wstepna.docx
  ├── makieta-checkout.html
  └── schemat-bazy.sql
```

`claude-planner` czyta ten folder sam (Read/Glob/Grep) — nic nie trzeba streszczać ręcznie.

## 2. (opcjonalnie) nowy profil, jeśli stack jest nietypowy

16 wbudowanych profili (`claude-planner profiles list`) pokrywa większość projektów.
Dla czegoś spoza listy (np. Ruby on Rails):

```bash
claude-planner profiles create "Ruby on Rails + Sidekiq + PostgreSQL" \
  --id ruby-on-rails --model sonnet
```

Profil trafia do `~/.claude-planner/profiles/` i jest od razu dostępny w `init`.

## 3. `claude-planner init`

```bash
claude-planner init \
  --name "Sklep XYZ" \
  --client "Acme Sp. z o.o." \
  --output ~/projekty/sklep-xyz \
  --intake ~/software-house/clients/acme/sklep-xyz/intake \
  --profile web-fullstack --profile postgresql-pgvector-postgis \
  --model sonnet   # opus dla trudniejszych projektów, gdy jakość > czas/koszt
```

Bez flag pyta o wszystko interaktywnie, łącznie z modelem.

Pod maską:

1. **Analiza intake** — Claude czyta materiały i streszcza je (temat, technologie,
   encje bazy, ekrany z makiety, otwarte pytania).
2. **Wywiad discovery**, rola po roli, jedno pytanie na turę:

   ```
   ── Product Manager / Business Analyst ──────────────────────────
   Product Manager: Jaki jest główny problem biznesowy, który ma
   rozwiązać ten sklep?
   Twoja odpowiedź: Klient sprzedaje przez telefon/mail, chce
   automatyczny checkout i płatności online...
   [...]
   ── Architekt / Tech Lead ────────────────────────────────────────
   ── Backend / Frontend Developer ─────────────────────────────────
   ── QA / DevOps / UX ─────────────────────────────────────────────
   ```

   `koniec` w dowolnym momencie zamyka bieżący etap wcześniej (Claude podsumowuje
   ustalenia zamiast drążyć dalej).
3. **Generowanie** — Claude pisze `docs/vision.md`, `docs/prd.md`, `docs/roadmap.md`,
   `docs/coding-standards.md`, `docs/definition-of-done.md`, `docs/test-strategy.md`
   i ADR-y dla decyzji o wysokim koszcie zmiany.
4. **Scaffolding** — Python (bez LLM) generuje `.claude/agents/`, `.claude/skills/`,
   `.claude/commands/`, `.claude/hooks/`, `.claude/settings.json`, `CLAUDE.md`,
   `WORKFLOW.md`, `state.md`, robi `git init` + commit startowy.

## 4. Repo po `init`

```
sklep-xyz/
├── CLAUDE.md                       # wejście dla Claude Code: agenci, komendy, zasady
├── WORKFLOW.md                     # instrukcja "od A do Z" dla tego projektu
├── README.md
├── state.md                        # jedyne źródło prawdy o stanie (nadpisywane)
├── docs/
│   ├── vision.md / prd.md / roadmap.md
│   ├── coding-standards.md / definition-of-done.md / test-strategy.md
│   └── adr/ (template.md, README.md, 0001-...)
├── .planner/
│   ├── project.yaml                # metadane (klient, profile, data)
│   ├── brief.json                  # pełny brief (wejście dla `regenerate`)
│   ├── project-state.json          # pamięć wywiadu (fakty, skala, fatigue)
│   └── interview-transcript.md     # pełny zapis wywiadu (do wglądu, nie do edycji)
└── .claude/
    ├── settings.json                # hooki: SessionStart, PreToolUse (anty-halucynacja)
    ├── agents/                      # product-manager, architect, backend-frontend-dev,
    │                                # qa-devops-ux + agenci z profili (np. api-contract-guardian)
    ├── skills/                      # konwencje z profili (np. pgvector-search-conventions)
    ├── commands/                    # setup-dev-environment, new-adr, update-roadmap,
    │                                # update-state, log-decision, daily-standup, sprint-review
    └── hooks/
        └── check-pinned-dependency.py
```

## 5. Pierwsza sesja Claude Code

```bash
cd ~/projekty/sklep-xyz
claude
```

Pierwsza komenda: `/setup-dev-environment` — instaluje zależności wybranych profili
(pyta o potwierdzenie przy instalacji globalnej). Po zakończeniu otwórz **nową sesję**,
żeby LSP poprawnie się zainicjował.

## 6. Codzienna praca: implementacja feature'a

```
Ty: Zaimplementuj endpoint GET /api/products/{id}/recommendations
    zwracający 5 podobnych produktów na podstawie embeddingów.
```

Claude Code sam sięga po agenta `db-migration-guardian` i skill
`pgvector-search-conventions` (bo zadanie dotyczy wyszukiwania wektorowego) — kod
wychodzi zgodny z konwencją projektu, nie "z pamięci".

Nowa zależność z przypiętą wersją jest blokowana:

```
Claude: [pip install sentence-transformers==2.7.0]
BLOKADA (check-pinned-dependency): nie zgaduj wersji z pamięci — usuń przypięcie,
sprawdź realną wersję menedżerem pakietów, albo zapytaj użytkownika.
```

Claude instaluje bez przypięcia albo pyta wprost o wersję — nigdy nie wpisuje jej z głowy.

## 7. Dokumentowanie decyzji

```
Ty: /new-adr przejście z indeksu IVFFlat na HNSW dla wyszukiwania podobieństwa produktów
```

Claude sprawdza kolejny wolny numer w `docs/adr/README.md`, dopytuje o brakujący
kontekst, zapisuje ADR i aktualizuje indeks.

Dla drobniejszych ustaleń:

```
Ty: /log-decision limit rekomendacji ustawiamy na stałe 5, bez paginacji na start
```

## 8. Śledzenie postępu

```
Ty: /daily-standup
```

```
Zrobione: endpoint /recommendations (pgvector, HNSW), testy jednostkowe embeddingów
W trakcie: integracja frontend -> nowy endpoint
Blockery: brak
```

Efemeryczne — nic nie zapisuje do repo. Na koniec fazy:

```
Ty: /sprint-review
```

pokazuje postęp względem `docs/roadmap.md` i proponuje `/update-roadmap`/`/update-state`.
Rób `/update-state` po każdym istotnym kroku — jedyny sposób aktualizacji `state.md`
(nadpisywanego w całości, żeby nie puchł z czasem).

## 9. Wdrożenie

`claude-planner` generuje tylko artefakty planistyczne — bez CI/CD ani skryptów
deployu (celowo, patrz `README.md`). W praktyce:

1. `docs/roadmap.md` ma jawną fazę "Wdrożenie MVP" jako kamień milowy.
2. `docs/definition-of-done.md` musi być spełnione dla całego zakresu wydania.
3. Decyzje o środowiskach/strategii wdrożenia dokumentujesz jako ADR *przed* wdrożeniem.
4. Po wdrożeniu: `/update-state` z nową fazą projektu.

## 10. Kolejna iteracja

Zespół wraca do `docs/roadmap.md`, wybiera kolejną fazę, pętla z kroku 6 zaczyna się
od nowa — środowisko wygenerowane raz w kroku 3 żyje z projektem tak długo, jak trwa
jego rozwój.
