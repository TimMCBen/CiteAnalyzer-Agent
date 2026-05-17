from __future__ import annotations

import json
from typing import Any
from urllib import parse, request

from packages.shared.network_retry import RetryPolicy, retry_call
from packages.shared.runtime_logging import get_runtime_logger


class OpenAlexClient:
    BASE_URL = "https://api.openalex.org"

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        max_attempts: int = 3,
        retry_base_delay_seconds: float = 0.5,
        retry_jitter_seconds: float = 0.2,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._retry_policy = RetryPolicy(
            service="OpenAlex",
            operation="作者查询",
            max_attempts=max_attempts,
            base_delay_seconds=retry_base_delay_seconds,
            max_delay_seconds=3.0,
            jitter_seconds=retry_jitter_seconds,
            overall_budget_seconds=6.0,
            impact="single_author",
        )

    def lookup_author(self, name: str) -> dict[str, Any] | None:
        query = str(name or "").strip()
        if not query:
            return None

        get_runtime_logger().detail("openalex.lookup", "正在查询 OpenAlex 作者画像", author=query)
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
        payload = retry_call(
            lambda: self._read_json(req),
            self._retry_policy,
        )

        results = payload.get("results")
        if not isinstance(results, list) or not results:
            get_runtime_logger().detail("openalex.lookup", "OpenAlex 未返回作者候选", author=query)
            return None

        best = results[0]
        if not isinstance(best, dict):
            return None
        get_runtime_logger().detail(
            "openalex.lookup",
            "OpenAlex 返回作者候选",
            author=query,
            matched_name=best.get("display_name"),
        )
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

    def _read_json(self, req: request.Request) -> dict[str, Any]:
        with request.urlopen(req, timeout=self._timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except ValueError:
            return None
    return None
