# Game

Prosty projekt gry w Pythonie z rozdzieleniem warstw:
- `src/core` - logika i Orders (bez `pygame`)
- `src/ui` - implementacje menu (`console` i `pygame`)
- `src/app` - petla aplikacji i routing Orders

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

## Test coverage (CI)

Pipeline CI uruchamia `pytest` z `pytest-cov` i publikuje podsumowanie pokrycia w zakladce `Checks` (GitHub Step Summary).

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

## Wymagania

- Python 3.12+
- `pip`

## Docker Compose

Build i uruchomienie testow:

```bash
docker compose build
docker compose run --rm app pytest
docker compose run --rm app mutmut run
```