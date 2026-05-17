from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib import parse, request

from packages.paper_identity.models import CandidateAuthor, CandidateWork
from packages.paper_identity.clients.arxiv import normalize_arxiv_id
from packages.shared.network_retry import RetryPolicy, retry_call
from packages.shared.runtime_logging import get_runtime_logger


class OpenAlexWorkClient:
    BASE_URL = "https://api.openalex.org"

    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        max_attempts: int = 3,
        retry_base_delay_seconds: float = 0.5,
        retry_jitter_seconds: float = 0.2,
        api_key: str | None = None,
        mailto: str | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._api_key = (api_key or os.getenv("OPENALEX_API_KEY") or "").strip() or None
        self._mailto = (mailto or os.getenv("OPENALEX_MAILTO") or "").strip() or None
        self._retry_policy = RetryPolicy(
            service="OpenAlex",
            operation="论文身份查询",
            max_attempts=max_attempts,
            base_delay_seconds=retry_base_delay_seconds,
            max_delay_seconds=3.0,
            jitter_seconds=retry_jitter_seconds,
            overall_budget_seconds=8.0,
            impact="single_identity_lookup",
        )
        self._work_cache: dict[str, list[CandidateWork]] = {}
        self._author_cache: dict[str, dict[str, Any] | None] = {}
        self.request_count = 0
        self.http_attempt_count = 0

    def lookup_work_by_doi(self, doi: str | None) -> CandidateWork | None:
        clean_doi = _normalize_doi(doi)
        if not clean_doi:
            return None
        cache_key = f"doi:{clean_doi}"
        if cache_key not in self._work_cache:
            url = self._build_url("/works", {"filter": f"doi:{clean_doi}", "per-page": "1"})
            payload = self._get_json(url)
            self._work_cache[cache_key] = [_adapt_work(item) for item in _results(payload)]
        works = self._work_cache[cache_key]
        return works[0] if works else None

    def search_work_by_title(self, title: str, *, per_page: int = 3) -> list[CandidateWork]:
        query = str(title or "").strip()
        if not query:
            return []
        cache_key = f"title:{query.lower()}"
        if cache_key not in self._work_cache:
            url = self._build_url("/works", {"search": query, "per-page": str(max(1, min(per_page, 10)))})
            payload = self._get_json(url)
            self._work_cache[cache_key] = [_adapt_work(item) for item in _results(payload)]
        return list(self._work_cache[cache_key])

    def lookup_author_by_id(self, author_id: str | None) -> dict[str, Any] | None:
        clean_id = _normalize_openalex_id(author_id, prefix="A")
        if not clean_id:
            return None
        if clean_id not in self._author_cache:
            url = self._build_url(f"/authors/{parse.quote(clean_id)}", {})
            try:
                payload = self._get_json(url)
            except Exception:
                self._author_cache[clean_id] = None
            else:
                self._author_cache[clean_id] = _adapt_author(payload)
        return self._author_cache[clean_id]

    def _build_url(self, path: str, params: dict[str, str]) -> str:
        query_params = dict(params)
        if self._api_key:
            query_params["api_key"] = self._api_key
        if self._mailto:
            query_params["mailto"] = self._mailto
        query = parse.urlencode(query_params)
        return f"{self.BASE_URL}{path}" + (f"?{query}" if query else "")

    def _get_json(self, url: str) -> dict[str, Any]:
        get_runtime_logger().detail(
            "openalex.work",
            "正在请求 OpenAlex 论文身份候选",
            url=_redact_url(url),
            authenticated=bool(self._api_key),
        )
        req = request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "CiteAnalyzer-Agent/openalex-work-identity",
            },
            method="GET",
        )
        return retry_call(lambda: self._read_json(req), self._retry_policy)

    def _read_json(self, req: request.Request) -> dict[str, Any]:
        self.request_count += 1
        self.http_attempt_count += 1
        with request.urlopen(req, timeout=self._timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))


def _results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("results")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _redact_url(url: str) -> str:
    parsed = parse.urlparse(url)
    query = parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted_query = [
        (key, "[REDACTED]" if key.lower() in {"api_key", "mailto"} else value)
        for key, value in query
    ]
    return parse.urlunparse(parsed._replace(query=parse.urlencode(redacted_query)))


def _adapt_work(item: dict[str, Any]) -> CandidateWork:
    authors: list[CandidateAuthor] = []
    for authorship in list(item.get("authorships") or []):
        if not isinstance(authorship, dict):
            continue
        author = authorship.get("author") if isinstance(authorship.get("author"), dict) else {}
        institutions = [
            str(institution.get("display_name") or "").strip()
            for institution in list(authorship.get("institutions") or [])
            if isinstance(institution, dict) and str(institution.get("display_name") or "").strip()
        ]
        authors.append(
            CandidateAuthor(
                name=str(author.get("display_name") or authorship.get("raw_author_name") or "").strip(),
                author_id=str(author.get("id") or "").strip() or None,
                orcid=str(author.get("orcid") or "").strip() or None,
                raw_author_name=str(authorship.get("raw_author_name") or "").strip() or None,
                institutions=institutions,
                countries=[str(country) for country in list(authorship.get("countries") or []) if country],
            )
        )
    primary_location = item.get("primary_location") if isinstance(item.get("primary_location"), dict) else {}
    source = primary_location.get("source") if isinstance(primary_location.get("source"), dict) else {}
    url = str(primary_location.get("landing_page_url") or item.get("doi") or "").strip() or None
    pdf_url = str(primary_location.get("pdf_url") or "").strip() or None
    arxiv_id = normalize_arxiv_id(url or "") or normalize_arxiv_id(str(item.get("doi") or ""))
    return CandidateWork(
        source="openalex",
        work_id=str(item.get("id") or "").strip() or None,
        title=str(item.get("title") or item.get("display_name") or "").strip(),
        doi=str(item.get("doi") or "").replace("https://doi.org/", "").strip() or None,
        year=_coerce_int(item.get("publication_year")),
        work_type=str(item.get("type") or source.get("type") or "").strip() or None,
        url=url,
        pdf_url=pdf_url,
        arxiv_id=arxiv_id,
        authors=[author for author in authors if author.name or author.author_id],
    )


def _adapt_author(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "author_id": str(payload.get("id") or "").strip(),
        "name": str(payload.get("display_name") or "").strip(),
        "affiliations": [
            str(institution.get("display_name") or "").strip()
            for institution in list(payload.get("last_known_institutions") or [])
            if isinstance(institution, dict) and str(institution.get("display_name") or "").strip()
        ],
        "fields": [
            str(concept.get("display_name") or "").strip()
            for concept in list(payload.get("x_concepts") or [])
            if isinstance(concept, dict) and str(concept.get("display_name") or "").strip()
        ][:5],
        "h_index": _coerce_int((payload.get("summary_stats") or {}).get("h_index")),
        "citation_count": _coerce_int(payload.get("cited_by_count")),
        "works_count": _coerce_int(payload.get("works_count")),
        "source_ids": {"openalex": str(payload.get("id") or "").strip()},
        "evidence_sources": ["openalex_author_id"],
    }


def _normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    text = str(doi).strip()
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text, flags=re.IGNORECASE)
    return text.lower() or None


def _normalize_openalex_id(value: str | None, *, prefix: str) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    match = re.search(rf"{prefix}\d+", text, re.IGNORECASE)
    if match:
        return match.group(0).upper()
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except ValueError:
            return None
    return None
