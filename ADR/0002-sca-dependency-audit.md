# ADR 0002: Wprowadzenie SCA dla zaleznosci

- Status: Accepted
- Data: 2026-03-07

## Kontekst

Projekt ma testy jednostkowe, coverage i testy mutacyjne, ale brakowalo stalego sprawdzania znanych podatnosci w zaleznosciach.

## Decyzja

Dodajemy Software Composition Analysis (SCA) oparte o `pip-audit`:

- zaleznosc `pip-audit` w `requirements.txt`,
- osobna usluga `sca` w `docker-compose.yml`,
- automatyczne uruchamianie skanu w CI (`.github/workflows/ci.yml`) przed testami,
- publikacja wyniku skanu w `GitHub Step Summary`,
- bramka jakosci: znalezienie podatnosci powoduje blad pipeline.

## Konsekwencje

Pozytywne:

- wczesne wykrywanie znanych CVE w zaleznosciach,
- dodatkowa, automatyczna kontrola jakosci bez zmian w kodzie aplikacji.

Negatywne:

- mozliwe czestsze aktualizacje zaleznosci po wykryciu podatnosci,
- wydluzenie czasu pipeline o krok skanowania.

## Rozwazone alternatywy

- brak SCA i poleganie tylko na testach, odrzucone (testy nie wykrywaja CVE w bibliotekach),
- narzedzia zewnetrzne inne niz `pip-audit`, odrzucone na tym etapie na rzecz prostszej integracji z Python/pip.
