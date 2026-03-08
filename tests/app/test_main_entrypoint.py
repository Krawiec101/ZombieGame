from __future__ import annotations

import runpy

import app.app as app_module


def test_main_module_calls_app_run(monkeypatch) -> None:
    calls = 0

    def fake_run() -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(app_module, "run", fake_run)

    runpy.run_module("main", run_name="__main__")

    assert calls == 1
