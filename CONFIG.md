# Konfiguracja `claude-planner.json`

`claude-planner init` przyjmuje wszystkie swoje argumenty również jako plik
JSON — odpowiednik `package.json` dla `npm init`. Pozwala to raz zapisać
ustawienia projektu (nazwę, klienta, profile, model itd.) i uruchamiać
`init` bez powtarzania flag przy każdym wywołaniu, np. w skrypcie CI albo
gdy wielu członków zespołu odtwarza to samo środowisko.

Gotowy przykład: [`claude-planner.example.json`](./claude-planner.example.json)
— skopiuj go jako `claude-planner.json` i dostosuj do projektu.

## Jak jest wczytywany

1. Jeśli podasz `--config <ścieżka>` / `-c <ścieżka>`, użyty zostanie dokładnie
   ten plik (błąd, jeśli nie istnieje).
2. W przeciwnym razie `init` szuka pliku `claude-planner.json` w bieżącym
   katalogu roboczym. Jeśli go nie znajdzie, po prostu pomija ten krok
   (zero zmian w zachowaniu — działa tak jak wcześniej).
3. **Pierwszeństwo:** flaga CLI > wartość z pliku konfiguracyjnego > pytanie
   interaktywne. Możesz więc trzymać większość ustawień w pliku i nadpisać
   pojedynczą wartość flagą przy konkretnym uruchomieniu, np.:

   ```bash
   claude-planner init --config ./claude-planner.json --model opus
   ```

Pola, których nie podasz ani flagą, ani w pliku, są dopytywane interaktywnie
tak jak dotychczas.

## Pola

Wszystkie pola są opcjonalne — brakujące są dopytywane interaktywnie (albo,
w przypadku `intake`, po prostu pomijane).

| Pole            | Typ              | Odpowiednik flagi CLI    | Opis                                                                                          |
|-----------------|------------------|---------------------------|------------------------------------------------------------------------------------------------|
| `name`          | `string`         | `--name`                  | Nazwa projektu.                                                                                 |
| `client`        | `string`         | `--client`                | Nazwa klienta.                                                                                  |
| `output`        | `string` (ścieżka) | `--output` / `-o`       | Ścieżka, w której zostanie utworzone nowe repo projektu. Może być względna wobec katalogu, z którego uruchamiasz `init`. |
| `intake`        | `string` (ścieżka) | `--intake`               | Ścieżka do folderu z materiałami od klienta (spec, MVP, makiety, schemat DB itd.). Musi wskazywać na istniejący folder. |
| `profiles`      | `string[]`       | `--profile` / `-p` (wielokrotnie) | Lista ID profili technologicznych, np. `["web-fullstack", "postgresql-pgvector-postgis"]`. Zobacz `claude-planner profiles list`. |
| `profiles_dir`  | `string` (ścieżka) | `--profiles-dir`        | Katalog z własnymi profilami (oprócz wbudowanych). Domyślnie `~/.claude-planner/profiles`.     |
| `model`         | `"sonnet"` \| `"opus"` | `--model`             | Model Claude użyty w wywiadzie i generowaniu środowiska.                                        |

Nieznane pola powodują błąd walidacji (literówki w kluczach nie zostaną po
cichu zignorowane).

## Przykład

```json
{
  "name": "Sklep XYZ",
  "client": "Acme Sp. z o.o.",
  "output": "./sklep-xyz",
  "intake": "./intake",
  "profiles": ["web-fullstack", "postgresql-pgvector-postgis"],
  "profiles_dir": "~/.claude-planner/profiles",
  "model": "sonnet"
}
```

Z takim plikiem `claude-planner.json` w bieżącym katalogu wystarczy:

```bash
claude-planner init
```

żeby uruchomić `init` bez żadnych pytań (poza ostatecznym potwierdzeniem
"Rozpocząć wywiad i generowanie środowiska?").
