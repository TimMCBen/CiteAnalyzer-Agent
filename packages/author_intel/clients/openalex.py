from __future__ import annotations

import json
from typing import Any
from urllib import parse, request


class OpenAlexClient:
    BASE_URL = "https://api.openalex.org"

    def lookup_author(self, name: str) -> dict[str, Any] | None:
        query = str(name or "").strip()
        if not query:
            return None

        url = (
            f"{self.BASE_URL}/authors?"
            f"{parse.urlencode({'search': query, 'per-page': '3'})}"
        )
        req = request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "CiteAnalyzer-Agent/openalex-author-intel",
            },
            method="GET",
        )
        with request.urlopen(req, timeout=15.0) as response:
            payload = json.loads(response.read().decode("utf-8"))

        results = payload.get("results")
        if not isinstance(results, list) or not results:
            return None

        best = results[0]
        if not isinstance(best, dict):
            return None
        return {
            "author_id": str(best.get("id") or "").strip(),
            "name": str(best.get("display_name") or query).strip(),
            "affiliations": [
                institution_name
                for institution in list(best.get("last_known_institutions") or [])
                if isinstance(institution, dict)
                for institution_name in [str(institution.get("display_name") or "").strip()]
                if institution_name
            ],
            "fields": [
                field_name
                for concept in list(best.get("x_concepts") or [])
                if isinstance(concept, dict)
                for field_name in [str(concept.get("display_name") or "").strip()]
                if field_name
            ][:5],
            "h_index": _coerce_int((best.get("summary_stats") or {}).get("h_index")),
            "citation_count": _coerce_int(best.get("cited_by_count")),
            "works_count": _coerce_int(best.get("works_count")),
            "source_ids": {"openalex": str(best.get("id") or "").strip()},
            "evidence_sources": ["openalex"],
        }


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except ValueError:
            return None
    return None
