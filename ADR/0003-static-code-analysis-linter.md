# ADR 0003: Statyczna analiza kodu (linter)

- Status: Accepted
- Data: 2026-03-07

## Kontekst

Projekt ma testy, coverage, testy mutacyjne oraz audit zaleznosci, ale brakowalo automatycznej statycznej analizy kodu.

## Decyzja

Dodajemy linter `ruff` jako element SCA (statyczna analiza kodu):

- zaleznosc `ruff` w `requirements.txt`,
- konfiguracja `ruff` w `pyproject.toml`,
- osobna usluga `lint` w `docker-compose.yml`,
- automatyczne uruchamianie lintera w CI (`.github/workflows/ci.yml`) przed testami,
- publikacja wyniku lintera w `GitHub Step Summary`.

## Konsekwencje

Pozytywne:

- szybsze wykrywanie bledow statycznych i niespojnosci stylu,
- dodatkowa bramka jakosci uruchamiana automatycznie.

Negatywne:

- koniecznosc utrzymania konfiguracji lintera,
- potencjalne poprawki porzadkowe przy zmianach w kodzie.

## Rozwazone alternatywy

- brak lintera i poleganie wylacznie na testach uruchomieniowych,
- inne lintery Pythona, odrzucone na tym etapie na rzecz szybkosci i prostoty `ruff`.
