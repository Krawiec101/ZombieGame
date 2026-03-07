# ADR 0004: Rozdzielenie UI i logiki biznesowej przez zdarzenia

- Status: Accepted
- Data: 2026-03-07

## Kontekst

Projekt mial juz podstawowy podzial `app/core/ui`, ale granice miedzy warstwami nie byly egzekwowane automatycznie.
UI i app operowaly na wspolnym modelu `Order`, a brak testow architektury utrudnial wykrywanie naruszen przy dalszym rozwoju.

## Decyzja

Wprowadzamy minimalny model warstwowy oparty o zdarzenia:

- `src/contracts` zawiera kontrakty komunikacji (`UIEvent`, `DomainEvent`, `MainMenuView`),
- UI emituje `UIEvent`, nie uruchamia bezposrednio logiki biznesowej,
- Core mapuje `UIEvent -> DomainEvent` (bez zaleznosci od UI i `pygame`),
- App pelni role orchestratora i spina UI z Core przez routing zdarzen,
- import `pygame` jest lazy w widoku pygame (w czasie inicjalizacji widoku).

Dodatkowo zasady architektury sa egzekwowane testami `PyTestArch` uruchamianymi przez `pytest` lokalnie i w istniejacym CI.

## Konsekwencje

Pozytywne:

- wyrazniejsze granice miedzy warstwami i prostszy przeplyw sterowania,
- latwiejsze testowanie logiki bez uruchamiania UI/pygame,
- automatyczne wykrywanie naruszen architektury w CI.

Negatywne:

- dodatkowa warstwa kontraktow (`src/contracts`) i testy architektury do utrzymania,
- wiecej jawnych typow zdarzen przy rozwoju kolejnych ekranow/przeplywow.

## Rozwazone alternatywy

- pozostanie przy obecnym modelu bez twardych testow architektury, odrzucone (ryzyko dryfu architektonicznego),
- pelny rewrite aplikacji i routing stanu, odrzucone (zbyt duzy zakres na obecnym etapie).
