# Game

Prosty projekt gry w Pythonie z rozdzieleniem warstw:
- `src/core` - logika biznesowa menu i mapowanie `UIEvent -> DomainEvent` (bez `pygame`)
- `src/ui` - implementacje menu (`console` i `pygame`), bez wywolywania logiki core bezposrednio
- `src/app` - orchestrator spinajacy UI i Core (petla aplikacji + routing zdarzen)
- `src/contracts` - wspolne kontrakty zdarzen i interfejsow miedzy warstwami

Komunikacja miedzy warstwami odbywa sie przez zdarzenia:
- UI -> App/Core: `UIEvent` (komendy uzytkownika)
- Core -> App/UI: `DomainEvent` (decyzje/routing)

`pygame` jest importowany lazy w warstwie UI (dopiero przy tworzeniu widoku pygame), co pozwala uruchamiac testy w srodowiskach headless.

## Uruchomienie gry

Preferowany sposob uruchamiania z root repo:

```bash
python -m src.main
```

Na Windows (venv lokalny):

```bash
.\.venv\Scripts\python.exe -m src.main
```

## Wymuszenie menu konsolowego

Aby uruchomic bez `pygame` (np. headless/CI), ustaw zmienna:

```bash
GAME_USE_CONSOLE_MENU=1
```

Windows PowerShell:

```powershell
$env:GAME_USE_CONSOLE_MENU='1'; .\.venv\Scripts\python.exe -m src.main
```

## Testy

Testy nie wymagaja `pygame`:

```bash
.\.venv\Scripts\python.exe -m pytest -q
```

Tylko testy architektury (PyTestArch):

```bash
.\.venv\Scripts\python.exe -m pytest -q tests/architecture
```

## Test coverage (CI)

Pipeline CI uruchamia `pytest` z `pytest-cov` dla testow funkcjonalnych/jednostkowych oraz osobny krok dla testow architektury (`tests/architecture`, PyTestArch). Podsumowania sa publikowane w zakladce `Checks` (GitHub Step Summary).

## Testy mutacyjne

Projekt korzysta z `mutmut`:

```bash
python -m mutmut run
python -m mutmut results --all true
```

W CI jest ustawiona bramka jakosci mutacji:
- minimalny `mutation score`: `90%`
- `survived`: `0`
- `suspicious`: `0`
- `timeout`: `1`

## SCA (zaleznosci)

Projekt korzysta z `pip-audit` do skanowania podatnosci w zaleznosciach (`Software Composition Analysis`):

```bash
python -m pip_audit -r requirements.txt
```

W CI/CD skan uruchamia sie automatycznie przed testami. Wykrycie podatnosci powoduje blad pipeline.

## SCA (statyczna analiza kodu / linter)

Projekt korzysta z `ruff` do statycznej analizy kodu:

```bash
python -m ruff check src tests
```

W CI/CD linter uruchamia sie automatycznie przed testami. Wykrycie problemow powoduje blad pipeline.

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
```
