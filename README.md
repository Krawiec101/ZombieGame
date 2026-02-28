# Game

Prosty projekt gry w Pythonie z menu glownym opartym o `pygame`.

## Szybki start gry

Uruchom z katalogu glownego repozytorium:

```bash
python -m src.main
```

Na Windows mozesz tez uzyc:

```bash
py -m src.main
```

## Wymagania

- Python 3.12+
- `pip`

## Uruchomienie przez Docker Compose

Build i uruchomienie testow:

```bash
docker compose build
docker compose run --rm app pytest
```
