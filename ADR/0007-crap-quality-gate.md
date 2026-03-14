# ADR 0007: Bramka jakosci CRAP w CI

- Status: Accepted
- Data: 2026-03-14

## Kontekst

Projekt ma juz coverage, testy architektury, testy mutacyjne, audit zaleznosci i linter, ale brakowalo automatycznej kontroli laczacej zlozonosc funkcji z ich pokryciem testami.

## Decyzja

Dodajemy bramke jakosci CRAP (Change Risk Anti-Patterns) oparta o `radon` i `coverage.xml`:

- zaleznosc `radon` w `requirements.txt`,
- skrypt `scripts/ci/crap_gate.py` liczacy cyclomatic complexity, coverage per funkcja/metoda i wynik CRAP,
- automatyczne uruchamianie w CI (`.github/workflows/ci.yml`) po kroku `pytest` z coverage,
- publikacja raportu markdown do `GitHub Step Summary`,
- bramka jakosci z progami startowymi:
  - `max_crap_per_function = 30.0`,
  - `max_high_crap_functions = 0`,
  - `min_coverage_for_high_complexity = 80%`,
  - `high_complexity_threshold = 15`.

## Konsekwencje

Pozytywne:

- szybsze wykrywanie ryzykownych funkcji laczacych wysoka zlozonosc z niskim pokryciem,
- dodatkowa, automatyczna kontrola jakosci oparta o istniejacy raport coverage.

Negatywne:

- kolejny krok wydluzajacy pipeline,
- koniecznosc utrzymania progow i skryptu integracyjnego.

## Rozwazone alternatywy

- pozostanie przy samym globalnym coverage i testach mutacyjnych, odrzucone (nie wskazuja lokalnych hotspotow zlozonosc/pokrycie),
- inne narzedzia do metryk kodu, odrzucone na tym etapie na rzecz prostszej integracji `radon` z obecnym stosem Python/CI.
