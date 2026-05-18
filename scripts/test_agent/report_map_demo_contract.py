"""Validate the Stage 7 standalone world-map demo contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.test_agent.stage_logging import StageLogger


DEMO_PATH = REPO_ROOT / "scripts" / "dev" / "report_world_map_demo.html"
WORLD_GEOJSON_PATH = REPO_ROOT / "packages" / "reporting" / "static" / "world.geo.json"


def assert_report_map_demo_contract() -> dict[str, object]:
    """Check the demo and local GeoJSON required by the report map."""
    assert DEMO_PATH.exists(), DEMO_PATH
    assert WORLD_GEOJSON_PATH.exists(), WORLD_GEOJSON_PATH

    geojson = json.loads(WORLD_GEOJSON_PATH.read_text(encoding="utf-8"))
    assert geojson.get("type") == "FeatureCollection", geojson.keys()
    features = geojson.get("features", [])
    assert isinstance(features, list) and len(features) > 100, len(features)
    names = {
        feature.get("properties", {}).get("name")
        for feature in features
        if isinstance(feature, dict)
    }
    for name in ("China", "United States of America", "Singapore", "Hong Kong S.A.R.", "South Korea", "United Kingdom"):
        assert name in names, name

    demo = DEMO_PATH.read_text(encoding="utf-8")
    assert "echarts.registerMap" in demo
    assert 'type: "map"' in demo
    assert "visualMap" in demo
    assert "world.geo.json" in demo
    assert "China" in demo
    assert "United States of America" in demo
    assert "Unknown" in demo
    return {"demo_path": str(DEMO_PATH), "features": len(features)}


def main() -> None:
    """Run the world-map demo contract validation."""
    logger = StageLogger("report-map-demo")
    logger.start()
    detail = assert_report_map_demo_contract()
    logger.pass_case("demo_contract", detail=f"demo={detail['demo_path']} features={detail['features']}")
    logger.done("report map demo validation passed")


if __name__ == "__main__":
    main()
