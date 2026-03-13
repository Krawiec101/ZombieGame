# ADR 0005: Przeniesienie logiki rozgrywki z UI do Core przez GameSession

- Status: Accepted
- Data: 2026-03-11

## Kontekst

Po rozszerzeniu gry o jednostki, ruch i cele misji, czesc logiki domenowej trafila do `src/ui/game_views/pygame_game_view.py`.
Naruszalo to granice warstw (`ui` jako prezentacja) i powodowalo silne sprzezenie reguł gry z rendererem `pygame`.
Skutkiem ubocznym bylo trudniejsze testowanie logiki bez UI oraz ryzyko wyciekow stanu miedzy sesjami.

## Decyzja

Wprowadzamy `core.GameSession` jako centralny model i silnik kroku symulacji:

- `src/core/game_session.py` przejmuje:
  - stan mapy i jednostek,
  - selekcje jednostek i obsluge rozkazow,
  - ruch jednostek i tempo symulacji,
  - ewaluacje celow misji przez `core.mission_objectives`.
- `src/ui/game_views/pygame_game_view.py` pozostaje warstwa prezentacji:
  - pobiera snapshoty stanu z `GameSession`,
  - deleguje klikniecia do `GameSession`,
  - renderuje mape, jednostki, tooltipy i panel celow.
- `src/app/app.py` tworzy `GameSession` i wstrzykuje go do UI.

Dodatkowo usuwamy domenowe moduły z `ui` (m.in. `ui/game_views/units.py`) oraz egzekwujemy to testami architektury.

## Konsekwencje

Pozytywne:

- zgodnosc z granicami warstw (`core` zawiera logike biznesowa, `ui` prezentacje),
- prostsze i szybsze testy logiki bez `pygame`,
- latwiejsze rozszerzanie gameplayu (nowe jednostki/cele) bez modyfikacji rendererow.

Negatywne:

- wiecej kodu integracyjnego (`app` i adapter w `ui`),
- koniecznosc utrzymania snapshotowego API miedzy `core` i `ui`.

## Rozwazone alternatywy

- pozostawienie logiki w `ui` i dopisanie testow, odrzucone (utrwala naruszenie architektury),
- bezposredni import `core` przez `ui`, odrzucone (zwieksza sprzezenie i omija role `app` jako orchestratora).
