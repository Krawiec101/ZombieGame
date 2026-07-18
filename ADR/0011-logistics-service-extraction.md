# ADR 0011: Wydzielenie orkiestracji logistyki z GameSession

- Status: Accepted
- Data: 2026-07-18

## Kontekst

`core.GameSession` zawieral zarowno stan calej sesji, jak i szczegolowa orkiestracje sieci zaopatrzenia:
aktualizacje ladowisk, transportow oraz tras zaopatrzenia. Rosnaca liczba odpowiedzialnosci utrudniala dalsze
rozwijanie logistyki i niezalezne testowanie jej przeplywow.

Jednoczesnie istniejace metody aktualizacji `GameSession` sa uzywane jako stabilne punkty integracyjne w testach.
Wydzielenie logiki nie powinno usuwac tych punktow ani zmieniac zachowania kroku symulacji.

## Decyzja

Wprowadzamy pakiet `core.logistics`:

- `SupplyRouteManager` odpowiada za reguly i stan tras zaopatrzenia,
- `SupplyNetworkService` orkiestruje aktualizacje ladowisk, transportow i tras,
- `LogisticsPort` definiuje jawny kontrakt dostepu uslugi do stanu sesji.

`GameSession` implementuje port i pozostaje wlascicielem stanu. Dotychczasowe prywatne metody aktualizacji pozostaja
cienkimi delegatami do uslugi, dzieki czemu zachowujemy kompatybilnosc punktow integracyjnych bez duplikowania logiki.

## Konsekwencje

Pozytywne:

- mniejsza odpowiedzialnosc `GameSession`,
- jawna granica miedzy stanem sesji a orkiestracja logistyki,
- mozliwosc rozwijania i testowania logistyki jako osobnego obszaru domenowego,
- zachowanie kompatybilnosci istniejacych testow i rozszerzen sesji.

Negatywne:

- dodatkowy kontrakt i metody delegujace do utrzymania,
- czesc operacji logistycznych nadal wymaga dostepu do szerokiego stanu sesji przez port.

## Rozwazone alternatywy

- pozostawienie calej orkiestracji w `GameSession`, odrzucone z powodu dalszego wzrostu odpowiedzialnosci klasy,
- przeniesienie stanu logistyki do uslugi, odrzucone, poniewaz tworzyloby drugiego wlasciciela stanu sesji,
- bezposredni dostep uslugi do prywatnych pol `GameSession`, odrzucone na rzecz jawnego i testowalnego kontraktu portu.
