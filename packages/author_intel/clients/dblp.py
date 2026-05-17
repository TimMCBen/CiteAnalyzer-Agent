"""Client helpers for DBLP operations in author intelligence."""
from __future__ import annotations

import json
from typing import Any
from urllib import parse, request

from packages.shared.network_retry import RetryPolicy, retry_call


class DBLPClient:
    """Client wrapper for d b l p operations used by author intelligence."""
    BASE_URL = "https://dblp.org/search/author/api"

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        max_attempts: int = 2,
        retry_base_delay_seconds: float = 0.5,
        retry_jitter_seconds: float = 0.2,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._retry_policy = RetryPolicy(
            service="DBLP",
            operation="作者查询",
            max_attempts=max_attempts,
            base_delay_seconds=retry_base_delay_seconds,
            max_delay_seconds=2.0,
            jitter_seconds=retry_jitter_seconds,
            overall_budget_seconds=4.0,
            impact="single_author",
        )

    def lookup_author(self, name: str) -> dict[str, Any] | None:
        """Look up author for d b l p client."""
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
        payload = retry_call(
            lambda: self._read_json(req),
            self._retry_policy,
        )

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

    def _read_json(self, req: request.Request) -> dict[str, Any]:
        """Read JSON for d b l p client."""
        with request.urlopen(req, timeout=self._timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
