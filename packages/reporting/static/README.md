# Reporting Static Map Data

`world.geo.json` is a country-level GeoJSON file used by the Stage 7 HTML report
to render the citation-source world map with Apache ECharts.

## Source

- Dataset: DataHub `geo-countries`
- Upstream source: Natural Earth country boundaries
- URL used: `https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson`
- Retrieved for this repository: 2026-05-18
- Local processing: simplified with `scripts/dev/simplify_world_geojson.py` to keep
  generated HTML reports small enough for local opening and CI validation.

## License

The DataHub `geo-countries` package is published under the Open Data Commons
Public Domain Dedication and License, and the underlying Natural Earth data is
public domain. Keep this file on a clearly open/public-domain map source. Do not
replace it with arbitrary map data unless the license is checked and documented.

## Report Usage

The report renderer embeds this GeoJSON into generated `report.html` files so the
map works when the report is opened directly from the local filesystem. The
embedded map is only used for country-level aggregation; unknown or unmapped
regions are shown as text notes rather than forced into a country.
