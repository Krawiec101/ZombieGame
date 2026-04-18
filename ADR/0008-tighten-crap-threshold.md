# ADR 0008: Zaostrzenie progu CRAP

- Status: Accepted
- Data: 2026-04-18

## Kontekst

Po wdrozeniu bramki CRAP z progiem startowym `30.0` projekt utrzymywal wysoki poziom pokrycia testami i nie wykazywal szerokiego problemu z nadmierna zlozonoscia funkcji. Analiza aktualnego raportu pokazala, ze prog `30.0` zostawia zbyt duzy zapas i nie wymusza poprawy lokalnych hotspotow, zwlaszcza w warstwie UI.

## Decyzja

Zaostrzamy domyslny prog bramki CRAP:

- `max_crap_per_function` zmieniamy z `30.0` na `12.0`,
- pozostawiamy bez zmian:
  - `max_high_crap_functions = 0`,
  - `min_coverage_for_high_complexity = 80%`,
  - `high_complexity_threshold = 15`.

Dodatkowo porzadkujemy hotspoty w warstwie UI, aby nowy prog odzwierciedlal oczekiwany poziom jakosci juz w aktualnym kodzie i pozostawial niewielki zapas wzgledem granicy bramki.

## Konsekwencje

Pozytywne:

- bramka szybciej wykrywa lokalne miejsca, gdzie umiarkowana zlozonosc laczy sie z niewystarczajacym pokryciem,
- prog lepiej odpowiada aktualnemu stanowi kodu i wymusza utrzymanie malych metod pomocniczych,
- projekt przechodzi zaostrzona bramke bez pogarszania pokrycia testami.

Negatywne:

- nawet male rozbudowy metod obslugujacych wiele trybow beda szybciej wymagaly ekstrakcji helperow,
- prog wymaga regularnej rewizji przy rozwoju UI i logiki aplikacyjnej.

## Rozwazone alternatywy

- pozostawienie `30.0`, odrzucone (prog jest zbyt lagodny wobec aktualnego stanu projektu),
- ustawienie `12.0` bez refaktoru hotspotow, odrzucone (pozostawialoby zerowy lub zbyt maly margines bezpieczenstwa),
- zejscie od razu ponizej `12.0`, odrzucone na tym etapie jako zbyt agresywne.
