# Game

Prosty projekt gry w Pythonie z menu glownym i dwoma implementacjami widoku:
- `pygame` (domyslnie)
- fallback konsolowy

## Szybki start

Uruchom z katalogu glownego repozytorium:

```bash
python -m src.main
```

Na Windows mozesz tez uzyc:

```bash
py -m src.main
```

## Testy

```bash
python -m pytest -q
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
