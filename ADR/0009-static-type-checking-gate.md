# ADR 0009: Statyczna kontrola typow w CI

- Status: Accepted
- Data: 2026-04-19

## Kontekst

Projekt ma juz linter, coverage, CRAP, testy architektury, audit zaleznosci i testy mutacyjne, ale brakowalo twardej bramki sprawdzajacej zgodnosc typow w kodzie produkcyjnym.
Adnotacje typow istnialy juz w kontraktach i czesci logiki aplikacji, jednak ich poprawnosci nie egzekwowano automatycznie, wiec bledy typow nadal mogly trafic do review lub wychodzic dopiero w testach uruchomieniowych.

## Decyzja

Dodajemy statyczny type-checking oparty o `mypy`:

- zaleznosc `mypy` w `requirements.txt`,
- konfiguracja `mypy` w `pyproject.toml`,
- osobna usluga `typecheck` w `docker-compose.yml`,
- automatyczne uruchamianie type-checkingu w CI (`.github/workflows/ci.yml`) przed testami,
- publikacja wyniku do `GitHub Step Summary`,
- sprawdzanie calego kodu produkcyjnego w `src`.

Dodatkowo zaostrzamy bramke coverage przez ustawienie `--cov-fail-under=95`, aby deklarowany minimalny poziom pokrycia byl egzekwowany automatycznie, a nie tylko raportowany.

## Konsekwencje

Pozytywne:

- szybsze wykrywanie niezgodnosci kontraktow i bledow na granicach warstw,
- mniejsza potrzeba recznego sprawdzania adnotacji typow podczas review,
- lepsza zgodnosc miedzy deklarowanymi wymaganiami repo a realnymi bramkami CI,
- latwiejsze lokalne odtwarzanie pelnego zestawu kontroli jakosci.

Negatywne:

- kolejny krok wydluzajacy pipeline,
- koniecznosc utrzymywania konfiguracji `mypy` i stopniowego uszczelniania typow w bardziej dynamicznych obszarach UI,
- okazjonalne poprawki porzadkowe wymagane przez rozszerzone reguly statycznej analizy.

## Rozwazone alternatywy

- pozostanie przy samych adnotacjach bez type-checkera, odrzucone (nie daje automatycznej ochrony),
- `pyright`, odrzucone na tym etapie na rzecz prostszej integracji z obecnym stosem Python/venv/Docker,
- ograniczenie type-checkingu tylko do wybranych katalogow, odrzucone po sprawdzeniu, ze aktualny kod produkcyjny daje sie objac jedna bramka `mypy` po niewielkich poprawkach.
