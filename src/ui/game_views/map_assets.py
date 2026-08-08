from __future__ import annotations

from pathlib import Path
from typing import Any

_ASSET_DIRECTORY = Path(__file__).resolve().parents[1] / "assets" / "map"


class MapAssetCatalog:
    def __init__(self, *, pygame_module: Any) -> None:
        self._pygame = pygame_module
        self._sources: dict[str, Any | None] = {}
        self._scaled: dict[tuple[str, int, int], Any] = {}

    def draw_centered(
        self,
        *,
        screen: Any,
        asset_id: str,
        center: tuple[int, int],
        maximum_size: tuple[int, int],
    ) -> tuple[int, int] | None:
        image = self._scaled_image(asset_id=asset_id, maximum_size=maximum_size)
        if image is None:
            return None

        width, height = image.get_size()
        screen.blit(image, (center[0] - width // 2, center[1] - height // 2))
        return (width, height)

    def _scaled_image(self, *, asset_id: str, maximum_size: tuple[int, int]) -> Any | None:
        cache_key = (asset_id, maximum_size[0], maximum_size[1])
        if cache_key in self._scaled:
            return self._scaled[cache_key]

        source = self._source_image(asset_id)
        if source is None:
            return None

        source_width, source_height = source.get_size()
        scale = min(maximum_size[0] / source_width, maximum_size[1] / source_height)
        scaled_size = (
            max(1, round(source_width * scale)),
            max(1, round(source_height * scale)),
        )
        image = self._pygame.transform.smoothscale(source, scaled_size)
        self._scaled[cache_key] = image
        return image

    def _source_image(self, asset_id: str) -> Any | None:
        if asset_id in self._sources:
            return self._sources[asset_id]

        image_module = getattr(self._pygame, "image", None)
        transform_module = getattr(self._pygame, "transform", None)
        if image_module is None or transform_module is None:
            self._sources[asset_id] = None
            return None

        asset_path = _ASSET_DIRECTORY / f"{asset_id}.png"
        try:
            image = image_module.load(str(asset_path)).convert_alpha()
        except (OSError, self._pygame.error):
            image = None
        if image is not None:
            image = self._trim_transparent_padding(image)
        self._sources[asset_id] = image
        return image

    @staticmethod
    def _trim_transparent_padding(image: Any) -> Any:
        get_bounding_rect = getattr(image, "get_bounding_rect", None)
        if get_bounding_rect is None:
            return image

        content_rect = get_bounding_rect(min_alpha=1)
        if content_rect.width <= 0 or content_rect.height <= 0:
            return image
        return image.subsurface(content_rect).copy()
