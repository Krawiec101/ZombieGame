# ADR 0010: Zaostrzenie progow jakosci po wydzieleniu helperow widokow UI

- Status: Accepted
- Data: 2026-04-22

## Kontekst

Projekt utrzymywal juz wysokie coverage, dodatni wynik bramki CRAP i stabilny mutation score, ale poprzednie progi zostawialy zbyt duzy margines wzgledem aktualnego stanu kodu.
Najwieksze hotspoty znajdowaly sie w widokach `pygame`, gdzie pojedyncze klasy laczyly renderowanie, budowanie tresci tooltipow i obsluge wielu trybow wejscia.

Po wydzieleniu helperow dla `src/ui/game_views` i `src/ui/menus`:

- spadla lokalna zlozonosc handlerow i metod pomocniczych widokow,
- poprawil sie zapas wzgledem bramki CRAP,
- mozliwe stalo sie dalsze zaostrzenie progow bez sztucznego omijania gate'ow.

## Decyzja

Zaostrzamy domyslne bramki jakosci w CI i lokalnym odtwarzaniu:

- coverage podnosimy z `>= 95%` do `>= 96%`,
- `max_crap_per_function` zmieniamy z `12.0` na `11.1`,
- wymagany mutation score zmieniamy z `> 92.0%` na `> 93.0%`.

Pozostawiamy bez zmian:

- `max_high_crap_functions = 0`,
- `min_coverage_for_high_complexity = 80%`,
- `high_complexity_threshold = 15`,
- limit `suspicious = 0`,
- limit `timeout = 1`.

## Konsekwencje

Pozytywne:

- UI szybciej sygnalizuje potrzebe dalszego wydzielania odpowiedzialnosci,
- globalne progi lepiej odzwierciedlaja realny poziom jakosci repo,
- nowe helpery widokow sa objete testami jednostkowymi i wzmacniaja mutation gate.

Negatywne:

- nawet niewielkie rozbudowy widokow `pygame` beda szybciej wymagaly ekstrakcji helperow lub dopisania testow,
- mutation gate pozostaje kosztownym krokiem i bedzie wymagal dalszego uszczelniania surviving mutants przy kolejnych zmianach.

## Rozwazone alternatywy

- pozostawienie poprzednich progow, odrzucone (za duzy zapas nie wymusza dalszej poprawy),
- zaostrzenie tylko coverage i mutation bez CRAP, odrzucone (widoki UI byly glownym argumentem za poprawa lokalnej zlozonosci),
- zejscie od razu do `max_crap_per_function <= 11.0` lub mutation score `> 94.0%`, odrzucone na tym etapie jako zbyt agresywne wzgledem aktualnego marginesu.
