# ADR 0006: Orkiestracja gameplayu w App przez zdarzenia i snapshoty stanu

- Status: Accepted
- Data: 2026-03-11

## Kontekst

Po ADR 0005 logika gameplayu zostala przeniesiona do `core.GameSession`, ale `ui` nadal wywolywalo metody sesji bezposrednio
(`handle_left_click`, `handle_right_click`, `reset`, `tick`, odczyt snapshotow).
To utrzymywalo wyciek logiki sterowania do warstwy prezentacji i oslabialo role `app` jako orchestratora.

## Decyzja

Uszczelniamy granice warstw dla gameplayu:

- `ui` emituje jedynie zdarzenia komend:
  - `GameLeftClickRequested`
  - `GameRightClickRequested`
  - `GameFrameSyncRequested`
- `app` obsluguje te komendy i wywoluje `GameSession`.
- `app` publikuje do `ui` zdarzenie `GameStateSynced` ze snapshotem stanu.
- `ui/game_views/pygame_game_view.py` dziala jako renderer stanu (`apply_game_state`, `clear_game_state`) i nie zna `GameSession`.

Dodatkowo testy architektury egzekwuja brak referencji do `game_session` w `PygameGameView` oraz brak bezposrednich wywolan
`handle_left_click`/`handle_right_click` z `PygameMainMenuView`.

## Konsekwencje

Pozytywne:

- prezentacja i wejscie uzytkownika sa odseparowane od logiki domenowej,
- `app` staje sie pojedynczym miejscem orkiestracji gameplayu,
- łatwiej utrzymac testowalny, event-driven przeplyw danych miedzy warstwami.

Negatywne:

- wiecej typow zdarzen i kodu mapujacego w `app`,
- potrzeba utrzymania kontraktu snapshotu (`GameStateSynced`) po obu stronach.

## Rozwazone alternatywy

- pozostawienie bezposrednich wywolan `GameSession` z `ui`, odrzucone (narusza granice warstw),
- przeniesienie całej orkiestracji gameplayu do `ui`, odrzucone (duplikuje role `app` i utrwala sprzezenie z rendererem).
