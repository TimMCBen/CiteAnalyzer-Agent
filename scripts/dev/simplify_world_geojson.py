"""Simplify the report world GeoJSON for lightweight local HTML embedding."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
WORLD_GEOJSON_PATH = REPO_ROOT / "packages" / "reporting" / "static" / "world.geo.json"
MAX_RING_POINTS = 80


def main() -> None:
    """Rewrite the local world GeoJSON with lower-detail country boundaries."""
    data = json.loads(WORLD_GEOJSON_PATH.read_text(encoding="utf-8"))
    for feature in data.get("features", []):
        properties = feature.get("properties", {})
        feature["properties"] = {
            "name": properties.get("name"),
            "ISO3166-1-Alpha-3": properties.get("ISO3166-1-Alpha-3"),
            "ISO3166-1-Alpha-2": properties.get("ISO3166-1-Alpha-2"),
        }
        feature["geometry"] = _simplify_geometry(feature.get("geometry"))
    WORLD_GEOJSON_PATH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"simplified={WORLD_GEOJSON_PATH} bytes={WORLD_GEOJSON_PATH.stat().st_size}")


def _simplify_geometry(geometry: Any) -> Any:
    """Simplify polygon rings without changing feature names or country counts."""
    if not isinstance(geometry, dict):
        return geometry
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon":
        return {"type": geometry_type, "coordinates": [_simplify_ring(ring) for ring in coordinates]}
    if geometry_type == "MultiPolygon":
        return {
            "type": geometry_type,
            "coordinates": [[_simplify_ring(ring) for ring in polygon] for polygon in coordinates],
        }
    return geometry


def _simplify_ring(ring: list[list[float]]) -> list[list[float]]:
    """Downsample one polygon ring while preserving closure."""
    if not ring:
        return ring
    core = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    step = max(1, len(core) // MAX_RING_POINTS)
    points = core[::step]
    if core and core[-1] not in points:
        points.append(core[-1])
    if len(points) < 3:
        points = core[:3]
    rounded = [[round(float(x), 3), round(float(y), 3)] for x, y in points]
    if rounded and rounded[0] != rounded[-1]:
        rounded.append(rounded[0])
    return rounded


if __name__ == "__main__":
    main()
