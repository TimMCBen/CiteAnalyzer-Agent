from __future__ import annotations

import json
from typing import Any
from urllib import parse, request


class DBLPClient:
    BASE_URL = "https://dblp.org/search/author/api"

    def lookup_author(self, name: str) -> dict[str, Any] | None:
        query = str(name or "").strip()
        if not query:
            return None

        url = (
            f"{self.BASE_URL}?"
            f"{parse.urlencode({'q': query, 'format': 'json', 'h': '3'})}"
        )
        req = request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "CiteAnalyzer-Agent/dblp-author-intel",
            },
            method="GET",
        )
        with request.urlopen(req, timeout=15.0) as response:
            payload = json.loads(response.read().decode("utf-8"))

        hits = (((payload.get("result") or {}).get("hits") or {}).get("hit"))
        if not hits:
            return None
        if isinstance(hits, dict):
            hits = [hits]
        if not isinstance(hits, list):
            return None

        best = hits[0]
        if not isinstance(best, dict):
            return None
        info = best.get("info")
        if not isinstance(info, dict):
            return None

        author_name = str(info.get("author") or query).strip()
        dblp_url = str(info.get("url") or "").strip()
        return {
            "author_id": dblp_url or author_name,
            "name": author_name,
            "affiliations": [],
            "fields": [],
            "h_index": None,
            "citation_count": None,
            "works_count": None,
            "source_ids": {"dblp": dblp_url} if dblp_url else {},
            "evidence_sources": ["dblp"],
        }
