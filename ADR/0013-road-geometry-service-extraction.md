# ADR 0013: Wydzielenie geometrii drog z sesji gry

- Status: Accepted
- Data: 2026-07-18

## Kontekst

`GameSession` odpowiadal jednoczesnie za orkiestracje sesji oraz budowanie geometrii drog: rozwiazywanie punktow
kontrolnych, interpolacje Catmull-Rom, ograniczanie wspolrzednych i deduplikacje punktow. Utrudnialo to testowanie
algorytmu niezaleznie od calego agregatu sesji i zwiekszalo liczbe jego odpowiedzialnosci.

## Decyzja

Wydzielamy bezstanowy `RoadGeometryService` do pakietu `core.navigation`. Serwis otrzymuje uklady drog, obiekty
mapy i jej rozmiar jako jawne argumenty, a `GameSession` jedynie deleguje budowanie drog. Format konfiguracji i
wynikowa reprezentacja drog pozostaja bez zmian.

## Konsekwencje

Pozytywne:

- geometria drog moze byc testowana bez uruchamiania calej sesji,
- `GameSession` ma mniej odpowiedzialnosci,
- algorytm pozostaje w warstwie `core`, w pakiecie nawigacji.

Negatywne:

- pojawia sie dodatkowy serwis i delegacja,
- slownikowy format konfiguracji drog nadal wykorzystuje `Any`.

## Rozwazone alternatywy

- pozostawienie metod w `GameSession`, odrzucone ze wzgledu na rosnacy rozmiar agregatu,
- dodanie geometrii do `NavigationService`, odrzucone, aby nie laczyc budowania mapy z planowaniem ruchu,
- wprowadzenie nowych typowanych modeli drog, odroczone jako osobna zmiana wykraczajaca poza bezpieczny refaktor.
