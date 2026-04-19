# Game

Prosty projekt gry w Pythonie z rozdzieleniem warstw:
- `src/core` - logika biznesowa i symulacja (menu, sesja gry, cele misji, ruch jednostek), bez `pygame`
- `src/core/model` - modele domenowe sesji gry
  - `src/core/model/units` - oddzialy, dowodcy i szablony wzmocnien
  - `src/core/model/buildings` - budynki, trasy zaopatrzenia i transporty
- `src/ui` - warstwa prezentacji, bez wywolywania logiki core bezposrednio:
  - `src/ui/menus` - menu glowne i menu kontekstowe w trakcie gry
  - `src/ui/game_views` - widoki renderujace rozgrywke na podstawie snapshotow stanu
- `src/app` - orchestrator spinajacy UI i Core (petla aplikacji + routing zdarzen)
- `src/contracts` - wspolne kontrakty zdarzen i interfejsow miedzy warstwami

Komunikacja miedzy warstwami odbywa sie przez zdarzenia:
- UI -> App: `UIEvent` (komendy uzytkownika)
- App -> Core: wywolania orchestration (`GameSession` i routing menu)
- Core/App -> UI: `DomainEvent` (routing i snapshoty stanu, np. `GameStateSynced`)

`pygame` jest importowany lazy w warstwie UI (dopiero przy tworzeniu widoku pygame), co pozwala uruchamiac testy w srodowiskach headless.

Domyslny scenariusz misji jest ladowany z pliku `src/core/scenarios/default_scenario.json`.
To tam znajduja sie zalozenia mapy oraz struktura kampanii: kolejne misje, ich etapy, stan poczatkowy, cele, raporty fabularne i miejsce na przyszle wydarzenia.

## Uruchomienie gry

Preferowany sposob uruchamiania z root repo:

```bash
python -m src.main
```

Na Windows (venv lokalny):

```bash
.\.venv\Scripts\python.exe -m src.main
```

Domyslnie widok `pygame` startuje w trybie pelnoekranowym. Jesli fullscreen nie jest dostepny,
aplikacja automatycznie przechodzi na okno `1280x720`.

## Wymuszenie menu konsolowego

Aby uruchomic bez `pygame` (np. headless/CI), ustaw zmienna:

```bash
GAME_USE_CONSOLE_MENU=1
```

Windows PowerShell:

```powershell
$env:GAME_USE_CONSOLE_MENU='1'; .\.venv\Scripts\python.exe -m src.main
```

## Wersje jezykowe (i18n)

Wszystkie napisy UI sa ladowane z `src/ui/locales/*.json`.

Domyslny jezyk to `pl`. Mozna wymusic inny kod jezyka zmienna:

```bash
GAME_LANGUAGE=pl
```

Windows PowerShell:

```powershell
$env:GAME_LANGUAGE='pl'; .\.venv\Scripts\python.exe -m src.main
```

## Testy

Preferowany lokalny sposob odtwarzania bramek CI to Docker:

```powershell
.\scripts\ci\local_check.ps1
```

Jesli chcesz odpalic pojedynczy krok lokalnie, uzywaj tych samych komend co CI:

```bash
docker compose build
docker compose run --rm sca
docker compose run --rm lint
docker compose run --rm typecheck
docker compose run --rm app pytest tests --ignore=mutants --ignore=tests/architecture --cov=src --cov-fail-under=95 --cov-report=term-missing --cov-report=xml:coverage.xml
docker compose run --rm app python scripts/ci/crap_gate.py --coverage-xml coverage.xml --source-dir src --summary-md crap-summary.md
docker compose run --rm app pytest -q tests/architecture
docker compose run --rm app mutmut run
docker compose run --rm app sh -lc "mutmut results --all true"
```

## Czyszczenie lokalnych artefaktow

Aby usunac lokalne cache i wygenerowane artefakty (`__pycache__`, cache testow, raporty CI, katalog `mutants`), uruchom:

```bash
.\.venv\Scripts\python.exe scripts/cleanup_local_artifacts.py
```

Tryb podgladu bez usuwania:

```bash
.\.venv\Scripts\python.exe scripts/cleanup_local_artifacts.py --dry-run
```

## Test coverage (CI)

Pipeline CI uruchamia `pytest` z `pytest-cov` dla testow funkcjonalnych/jednostkowych oraz osobny krok dla testow architektury (`tests/architecture`, PyTestArch). Podsumowania sa publikowane w zakladce `Checks` (GitHub Step Summary).

Globalna bramka coverage jest twarda:
- wymagane pokrycie: `>= 95%`

Po kroku coverage dziala tez bramka CRAP (Change Risk Anti-Patterns), liczona na podstawie `coverage.xml` i cyclomatic complexity z `radon`.
Progi startowe w CI:
- `max_crap_per_function = 12.0`
- `max_high_crap_functions = 0`
- `min_coverage_for_high_complexity = 80%`
- `high_complexity_threshold = 15`

## Testy mutacyjne

Projekt korzysta z `mutmut`:

```bash
python scripts/cleanup_local_artifacts.py
python -m mutmut run
python -m mutmut results --all true
```

Wazne: `mutmut` przechowuje wyniki w katalogu `mutants`, wiec do wiernego odtworzenia CI trzeba zaczynac od czystego stanu.
Bez usuniecia tego katalogu lokalny wynik moze byc tylko przyrostowy i nie pokaze rzeczywistej pelnej bramki mutacyjnej.

W CI jest ustawiona bramka jakosci mutacji:
- wymagany `mutation score`: `> 92%`
- `suspicious`: `0`
- `timeout`: `1`

## SCA (zaleznosci)

Projekt korzysta z `pip-audit` do skanowania podatnosci w zaleznosciach (`Software Composition Analysis`):

```bash
docker compose run --rm sca
```

W CI/CD skan uruchamia sie automatycznie przed testami. Wykrycie podatnosci powoduje blad pipeline.

## SCA (statyczna analiza kodu / linter)

Projekt korzysta z `ruff` do statycznej analizy kodu:

```bash
docker compose run --rm lint
```

W CI/CD linter uruchamia sie automatycznie przed testami. Wykrycie problemow powoduje blad pipeline.

Aktualnie `ruff` sprawdza m.in.:
- bledy i oczywiste problemy (`E`, `F`)
- typowe pulapki z `flake8-bugbear` (`B`)
- porzadek importow (`I`)
- mozliwe uproszczenia skladni i nowsza skladnie Pythona (`UP`)

## Type checking

Projekt korzysta z `mypy` do statycznego sprawdzania typow w kodzie produkcyjnym:

```bash
docker compose run --rm typecheck
```

W CI/CD type-checking uruchamia sie automatycznie przed testami.

## Wymagania

- Python 3.12+
- `pip`

## Docker Compose

Build i uruchomienie testow:

```bash
docker compose build
docker compose run --rm app pytest
docker compose run --rm app mutmut run
docker compose run --rm sca
docker compose run --rm lint
docker compose run --rm typecheck
```
