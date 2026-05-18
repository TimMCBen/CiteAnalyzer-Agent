"""Load and normalize country-level map data for Stage 7 reports."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


WORLD_GEOJSON_PATH = Path(__file__).resolve().parent / "static" / "world.geo.json"
UNKNOWN_COUNTRY_LABEL = "Unknown"

COUNTRY_NAME_ALIASES = {
    "United States": "United States of America",
    "USA": "United States of America",
    "U.S.": "United States of America",
    "US": "United States of America",
    "Hong Kong": "Hong Kong S.A.R.",
    "South Korea": "South Korea",
    "Republic of Korea": "South Korea",
    "UK": "United Kingdom",
    "United Kingdom": "United Kingdom",
    "Taiwan": "Taiwan",
}


@lru_cache(maxsize=1)
def load_world_geojson() -> dict[str, object]:
    """Read the local public-domain country GeoJSON used by ECharts maps."""
    return json.loads(WORLD_GEOJSON_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def supported_map_names() -> frozenset[str]:
    """Return country or region names present in the local GeoJSON file."""
    geojson = load_world_geojson()
    features = geojson.get("features", [])
    names = {
        str(feature.get("properties", {}).get("name"))
        for feature in features
        if isinstance(feature, dict) and feature.get("properties", {}).get("name")
    }
    return frozenset(names)


def normalize_country_for_map(country: str) -> str | None:
    """Convert report country buckets into names understood by the GeoJSON map."""
    normalized = country.strip()
    if not normalized or normalized == UNKNOWN_COUNTRY_LABEL:
        return None
    mapped = COUNTRY_NAME_ALIASES.get(normalized, normalized)
    if mapped in supported_map_names():
        return mapped
    return None


def build_country_map_payload(country_distribution: dict[str, int]) -> dict[str, object]:
    """Build ECharts map series data while preserving Unknown and unmapped counts."""
    map_counts: dict[str, int] = {}
    unknown_count = 0
    unmapped_items: dict[str, int] = {}

    for country, raw_count in country_distribution.items():
        count = int(raw_count)
        if count <= 0:
            continue
        map_name = normalize_country_for_map(country)
        if map_name:
            map_counts[map_name] = map_counts.get(map_name, 0) + count
        elif country == UNKNOWN_COUNTRY_LABEL:
            unknown_count += count
        else:
            unmapped_items[country] = unmapped_items.get(country, 0) + count

    items = [
        {"name": name, "value": count}
        for name, count in sorted(map_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "items": items,
        "unknownCount": unknown_count,
        "unmappedItems": [
            {"name": name, "value": count}
            for name, count in sorted(unmapped_items.items(), key=lambda item: (-item[1], item[0]))
        ],
        "maxValue": max(map_counts.values(), default=0),
    }
