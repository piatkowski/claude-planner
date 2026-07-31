# Workflow: `claude-planner` + Claude Code od `init` do wdrożenia

Ten dokument pokazuje **pełny, konkretny przykład** użycia `claude-planner` razem z
Claude Code — od pierwszego uruchomienia `init` po wdrożenie projektu na produkcję.
To narracja krok po kroku, nie referencja API (tę znajdziesz w `README.md`).

> Uwaga: gdy `claude-planner init` skończy generować środowisko, w katalogu **każdego**
> wygenerowanego projektu powstaje własny, konkretny `WORKFLOW.md` — dopasowany do
> wybranych profili, wygenerowanych agentów/skilli/komend tego konkretnego projektu.
> Ten plik (w repo `claude-planner`) to przykład dla całego narzędzia; tamten to
> instrukcja dla zespołu pracującego nad konkretnym projektem klienta.

Przykład w tym dokumencie: software house dostaje zlecenie na sklep internetowy
("Sklep XYZ") dla klienta "Acme Sp. z o.o." — web fullstack + PostgreSQL z pgvector
(rekomendacje produktów).

## Krok 0 — instalacja i sanity check

```bash
pipx install claude-planner   # albo: uv pip install -e . w tym repo
claude-planner doctor         # sprawdza, czy `claude` (Claude Code CLI) jest dostępny
```

## Krok 1 — przygotuj materiały od klienta (intake)

Materiały klienta trzymamy **poza** repo projektu — np. w workspace software house'u:

```
~/software-house/clients/acme/sklep-xyz/intake/
  ├── brief.txt              # notatki ze spotkania z klientem
  ├── specyfikacja-wstepna.docx
  ├── makieta-checkout.html
  └── schemat-bazy.sql
```

`claude-planner` sam przeczyta ten folder (narzędziami Read/Glob/Grep) — nie musisz
niczego kopiować ani streszczać ręcznie.

## Krok 2 — (opcjonalnie) dorzuć profil, jeśli stack jest nietypowy

16 wbudowanych profili (`claude-planner profiles list`) pokrywa większość projektów
software house'u. Jeśli trafia się coś spoza listy (np. Ruby on Rails), wygeneruj
nowy profil za pomocą Claude zamiast pisać YAML ręcznie:

```bash
claude-planner profiles create "Ruby on Rails + Sidekiq + PostgreSQL" \
  --id ruby-on-rails --model sonnet
```

Profil trafia do `~/.claude-planner/profiles/` i jest od razu dostępny w `init`
(`--profiles-dir`, domyślnie właśnie ten katalog).

## Krok 3 — `claude-planner init`

```bash
claude-planner init \
  --name "Sklep XYZ" \
  --client "Acme Sp. z o.o." \
  --output ~/projekty/sklep-xyz \
  --intake ~/software-house/clients/acme/sklep-xyz/intake \
  --profile web-fullstack --profile postgresql-pgvector-postgis \
  --model sonnet
```

(`--model opus` dla trudniejszych/większych projektów, gdzie zależy Ci bardziej na
jakości analizy niż na czasie/koszcie wywiadu i generowania.)

Bez flag `init` zapyta o wszystko interaktywnie — łącznie z modelem.

### Co się dzieje pod maską

1. **Analiza intake** — Claude czyta `brief.txt`, `specyfikacja-wstepna.docx`,
   `makieta-checkout.html`, `schemat-bazy.sql` i streszcza je (temat, sugerowane
   technologie, encje z bazy, ekrany z makiety, otwarte pytania).
2. **Wywiad discovery**, sekwencyjnie, rola po roli — każda pyta o jedno na turę:

   ```
   ── Product Manager / Business Analyst ──────────────────────────
   Product Manager: Jaki jest główny problem biznesowy, który ma
   rozwiązać ten sklep — co dziś klient robi ręcznie/nieefektywnie?
   Twoja odpowiedź: Klient sprzedaje przez telefon/mail, chce
   automatyczny checkout i płatności online...

   Product Manager: Jaka jest grupa docelowa i ile SKU planujecie
   na start?
   Twoja odpowiedź: B2C, ok. 300 produktów na start...
   [...]
   ── Architekt / Tech Lead ────────────────────────────────────────
   Architekt: Jakie są wymagania co do skalowalności — spodziewany
   ruch w szczycie (np. wyprzedaże)?
   [...]
   ── Backend / Frontend Developer ─────────────────────────────────
   ── QA / DevOps / UX ─────────────────────────────────────────────
   ```

   W dowolnym momencie możesz wpisać `koniec`, żeby zamknąć bieżący etap wcześniej —
   Claude podsumuje to, co już ustalono, zamiast drążyć dalej.
3. **Generowanie** — Claude (ten sam model co w wywiadzie) pisze `docs/vision.md`,
   `docs/prd.md`, `docs/roadmap.md`, `docs/coding-standards.md`,
   `docs/definition-of-done.md`, `docs/test-strategy.md` oraz ADR-y dla decyzji
   o wysokim koszcie zmiany (np. "Next.js + FastAPI zamiast Django", "pgvector do
   rekomendacji produktowych zamiast osobnego serwisu ML").
4. **Scaffolding** — Python (deterministycznie, bez LLM) generuje `.claude/agents/`,
   `.claude/skills/`, `.claude/commands/`, `.claude/hooks/`, `.claude/settings.json`,
   `CLAUDE.md`, `WORKFLOW.md`, `state.md`, robi `git init` + commit startowy.

## Krok 4 — co masz w repo po `init`

```
sklep-xyz/
├── CLAUDE.md                       # wejście dla Claude Code: agenci, komendy, zasady
├── WORKFLOW.md                     # instrukcja "od A do Z" DLA TEGO projektu
├── README.md
├── state.md                        # jedyne źródło prawdy o stanie (nadpisywane)
├── docs/
│   ├── vision.md
│   ├── prd.md
│   ├── roadmap.md
│   ├── coding-standards.md
│   ├── definition-of-done.md
│   ├── test-strategy.md
│   └── adr/
│       ├── template.md
│       ├── README.md
│       └── 0001-nextjs-fastapi-zamiast-django.md
├── .planner/
│   ├── project.yaml                # metadane (klient, profile, data)
│   ├── brief.json                  # pełny brief (wejście dla `regenerate`)
│   ├── project-state.json          # globalna pamięć wywiadu (Moduł 1: fakty, skala, fatigue)
│   └── interview-transcript.md     # pełny zapis wywiadu (do wglądu, nie do edycji)
└── .claude/
    ├── settings.json                # hooki: SessionStart (przypomnienie stanu), PreToolUse (anty-halucynacja wersji)
    ├── agents/
    │   ├── product-manager.md
    │   ├── architect.md
    │   ├── backend-frontend-dev.md
    │   ├── qa-devops-ux.md
    │   ├── api-contract-guardian.md      # z profilu web-fullstack
    │   └── db-migration-guardian.md      # z profilu postgresql-pgvector-postgis
    ├── skills/
    │   ├── frontend-component-conventions/SKILL.md
    │   ├── api-endpoint-conventions/SKILL.md
    │   ├── schema-design-conventions/SKILL.md
    │   └── pgvector-search-conventions/SKILL.md
    ├── commands/
    │   ├── setup-dev-environment.md
    │   ├── new-adr.md
    │   ├── update-roadmap.md
    │   ├── update-state.md
    │   ├── log-decision.md
    │   ├── daily-standup.md
    │   └── sprint-review.md
    └── hooks/
        └── check-pinned-dependency.py
```

## Krok 5 — pierwsza sesja Claude Code w nowym repo

```bash
cd ~/projekty/sklep-xyz
claude
```

Pierwsza komenda w nowej sesji:

```
/setup-dev-environment
```

Claude czyta `.claude/commands/setup-dev-environment.md`, widzi listę komend
bootstrapujących z obu profili (`npm install`, `pip install -e ".[dev]"`), pyta o
potwierdzenie jeśli coś wygląda na instalację globalną, uruchamia je po kolei.
Po zakończeniu: **otwórz nową sesję** — dopiero wtedy code intelligence (LSP) dla
TypeScriptu i Pythona w tym repo poprawnie się zainicjuje.

## Krok 6 — codzienna praca: implementacja feature'a

Przykład: implementujesz endpoint rekomendacji produktów oparty o pgvector.

```
Ty: Zaimplementuj endpoint GET /api/products/{id}/recommendations
    zwracający 5 podobnych produktów na podstawie embeddingów.
```

Co się dzieje:
- Claude Code automatycznie sięga po agenta `db-migration-guardian` (bo dotyka
  schematu/zapytań) i skill `pgvector-search-conventions` (bo to wyszukiwanie
  wektorowe) — nie musisz ich wywoływać ręcznie.
- Skill mówi Claude wprost: jawny wybór indeksu (IVFFlat/HNSW), metryka odległości,
  strategia re-embeddingu — więc dostajesz kod zgodny z konwencją tego projektu,
  a nie losowe podejście wybrane "z pamięci".

Jeśli zadanie wymaga nowej zależności (np. biblioteki do generowania embeddingów):

```
Claude: Chcę dodać `sentence-transformers` do zależności.
[Claude próbuje: pip install sentence-transformers==2.7.0]

BLOKADA (hook check-pinned-dependency): wykryto instalację zależności
z przypiętą wersją (pip)...
NIE zgaduj (nie halucynuj) numeru wersji z pamięci treningowej...
1. Usuń przypiętą wersję...
2. Sprawdź realnie dostępne wersje...
3. Zapytaj użytkownika...
```

Claude albo uruchamia `pip install sentence-transformers` bez przypięcia, albo pyta
Cię wprost: *"Jaką wersję sentence-transformers chcesz zainstalować?"* — nigdy nie
wpisuje numeru z głowy.

## Krok 7 — dokumentowanie decyzji w trakcie pracy

Podczas implementacji okazuje się, że IVFFlat nie wystarcza przy rosnącej liczbie
produktów i trzeba przejść na HNSW:

```
Ty: /new-adr przejście z indeksu IVFFlat na HNSW dla wyszukiwania podobieństwa produktów
```

Claude sprawdza kolejny wolny numer w `docs/adr/README.md`, dopytuje o kontekst,
jeśli czegoś brakuje, i zapisuje `docs/adr/0004-przejscie-z-ivfflat-na-hnsw.md` +
aktualizuje indeks.

Dla drobniejszych ustaleń (nie warte pełnego ADR):

```
Ty: /log-decision limit rekomendacji ustawiamy na stałe 5, bez paginacji na start
```

## Krok 8 — śledzenie postępu

Na koniec dnia / przed standupem:

```
Ty: /daily-standup
```

```
Zrobione: endpoint /recommendations (pgvector, HNSW), testy jednostkowe embeddingów
W trakcie: integracja frontend -> nowy endpoint
Blockery: brak
```

Nic nie zapisuje do repo — to efemeryczne podsumowanie w czacie. Kiedy faza się
kończy:

```
Ty: /sprint-review
```

pokazuje co zrealizowano względem `docs/roadmap.md` i pyta, czy uruchomić
`/update-roadmap` i/lub `/update-state`. Zawsze rób `/update-state` po istotnym
kroku — to jedyny sposób aktualizacji `state.md`, a plik jest **nadpisywany w
całości**, więc kolejna sesja (Twoja albo kolegi z zespołu) dostaje aktualny, a
nie napuchnięty od miesięcy, obraz stanu projektu.

## Krok 9 — wdrożenie

`claude-planner` generuje wyłącznie artefakty planistyczne — nie ma tu szkieletu
CI/CD ani skryptów deployu (to celowe, patrz `README.md`). W praktyce:

1. `docs/roadmap.md` powinien mieć jawną fazę "Wdrożenie MVP" jako kamień milowy —
   nie jest to efekt uboczny ostatniego commita przed weekendem.
2. Przed wdrożeniem: `docs/definition-of-done.md` musi być spełnione dla całego
   zakresu wydania (nie tylko pojedynczego PR-a).
3. Decyzje o środowiskach/strategii wdrożenia (np. "staging na Fly.io, produkcja na
   AWS ECS") dokumentujesz jako ADR *przed* wdrożeniem, nie po fakcie.
4. Po wdrożeniu: `/update-state` z nową fazą projektu ("Wdrożono MVP na produkcję,
   monitorujemy pierwsze zamówienia").

## Krok 10 — kolejna iteracja

Zespół wraca do `docs/roadmap.md`, wybiera kolejną fazę, i pętla z Kroku 6 zaczyna
się od nowa — środowisko wygenerowane raz w Kroku 3 żyje z projektem tak długo, jak
długo trwa jego rozwój.
