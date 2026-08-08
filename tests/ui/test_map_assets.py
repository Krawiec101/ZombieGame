from __future__ import annotations

from types import SimpleNamespace

from ui.game_views import map_assets
from ui.game_views.map_assets import MapAssetCatalog


class _Image:
    def __init__(self, size: tuple[int, int]) -> None:
        self._size = size
        self.converted = False

    def convert_alpha(self) -> _Image:
        self.converted = True
        return self

    def get_size(self) -> tuple[int, int]:
        return self._size


class _TransparentImage(_Image):
    def __init__(self, size: tuple[int, int]) -> None:
        super().__init__(size)
        self.cropped = _Image((40, 20))

    def get_bounding_rect(self, *, min_alpha: int) -> SimpleNamespace:
        assert min_alpha == 1
        return SimpleNamespace(width=40, height=20)

    def subsurface(self, _rect: object) -> SimpleNamespace:
        return SimpleNamespace(copy=lambda: self.cropped)


class _Screen:
    def __init__(self) -> None:
        self.blit_calls: list[tuple[object, tuple[int, int]]] = []

    def blit(self, image: object, position: tuple[int, int]) -> None:
        self.blit_calls.append((image, position))


def test_catalog_loads_scales_centers_and_caches_asset(monkeypatch) -> None:
    source = _Image((200, 100))
    scaled = _Image((80, 40))
    load_calls: list[str] = []
    scale_calls: list[tuple[object, tuple[int, int]]] = []
    pygame = SimpleNamespace(
        error=RuntimeError,
        image=SimpleNamespace(load=lambda path: load_calls.append(path) or source),
        transform=SimpleNamespace(
            smoothscale=lambda image, size: scale_calls.append((image, size)) or scaled,
        ),
    )
    screen = _Screen()
    catalog = MapAssetCatalog(pygame_module=pygame)

    assert catalog.draw_centered(
        screen=screen,
        asset_id="unit",
        center=(100, 80),
        maximum_size=(80, 80),
    )
    assert catalog.draw_centered(
        screen=screen,
        asset_id="unit",
        center=(100, 80),
        maximum_size=(80, 80),
    )

    assert source.converted
    assert len(load_calls) == 1
    assert scale_calls == [(source, (80, 40))]
    assert screen.blit_calls == [(scaled, (60, 60)), (scaled, (60, 60))]


def test_catalog_returns_false_when_pygame_image_support_is_unavailable() -> None:
    catalog = MapAssetCatalog(pygame_module=SimpleNamespace())

    assert not catalog.draw_centered(
        screen=_Screen(),
        asset_id="unit",
        center=(0, 0),
        maximum_size=(10, 10),
    )


def test_catalog_returns_false_when_asset_cannot_be_loaded(monkeypatch) -> None:
    monkeypatch.setattr(map_assets, "_ASSET_DIRECTORY", map_assets._ASSET_DIRECTORY / "missing")
    pygame = SimpleNamespace(
        error=RuntimeError,
        image=SimpleNamespace(load=lambda _path: (_ for _ in ()).throw(OSError())),
        transform=SimpleNamespace(),
    )

    assert not MapAssetCatalog(pygame_module=pygame).draw_centered(
        screen=_Screen(),
        asset_id="unit",
        center=(0, 0),
        maximum_size=(10, 10),
    )


def test_catalog_trims_transparent_padding_before_scaling() -> None:
    source = _TransparentImage((100, 100))
    scaled_sizes: list[tuple[int, int]] = []
    pygame = SimpleNamespace(
        error=RuntimeError,
        image=SimpleNamespace(load=lambda _path: source),
        transform=SimpleNamespace(
            smoothscale=lambda _image, size: scaled_sizes.append(size) or _Image(size),
        ),
    )

    assert MapAssetCatalog(pygame_module=pygame).draw_centered(
        screen=_Screen(),
        asset_id="unit",
        center=(20, 20),
        maximum_size=(80, 80),
    )
    assert scaled_sizes == [(80, 40)]
