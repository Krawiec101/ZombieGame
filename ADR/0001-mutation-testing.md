# ADR 0001: Wprowadzenie testow mutacyjnych

- Status: Accepted
- Data: 2026-03-03

## Kontekst

W projekcie istnialy testy jednostkowe uruchamiane przez `pytest`, ale brakowalo mechanizmu sprawdzajacego jak skutecznie testy wykrywaja subtelne zmiany logiki.

## Decyzja

Dodajemy testy mutacyjne oparte o `mutmut`:

- zaleznosc `mutmut` w `requirements.txt`,
- konfiguracja narzedzia w `pyproject.toml`,
- uruchomienie mutacji w CI/CD (`.github/workflows/ci.yml`),
- opis uruchamiania lokalnego i w Dockerze w `README.md`.

## Konsekwencje

Pozytywne:

- wieksza pewnosc, ze testy wykrywaja regresje logiczne,
- dodatkowa bramka jakosci w pipeline.

Negatywne:

- dluzszy czas wykonywania CI,
- koniecznosc utrzymywania konfiguracji `mutmut`.

## Rozwazone alternatywy

- pozostanie przy samym `pytest` bez mutacji,
- wdrozenie innego frameworka mutacyjnego (np. `cosmic-ray`), odrzucone ze wzgledu na wyzsza zlozonosc konfiguracji na obecnym etapie projektu.
