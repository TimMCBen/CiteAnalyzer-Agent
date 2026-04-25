from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Iterable
from urllib import error, parse, request

from packages.shared.models import TargetPaper


DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 1.0
DEFAULT_RESOLVE_FIELDS = (
    "paperId,title,externalIds,year,venue,url,authors.name"
)
DEFAULT_CITATION_FIELDS = (
    "citingPaper.paperId,citingPaper.title,citingPaper.externalIds,"
    "citingPaper.year,citingPaper.venue,citingPaper.abstract,"
    "citingPaper.url,citingPaper.authors.name"
)


@dataclass(frozen=True)
class _RequestConfig:
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS


class SemanticScholarClient:
    """Thin Graph API client for stage2 citation fetching."""

    base_url = "https://api.semanticscholar.org/graph/v1"

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
        api_key: str | None = None,
    ) -> None:
        self._config = _RequestConfig(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )
        self._api_key = api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY")

    def resolve_target_paper(
        self,
        target_paper: TargetPaper,
        *,
        fields: str = DEFAULT_RESOLVE_FIELDS,
    ) -> dict[str, object]:
        for paper_id in self._candidate_identifiers(target_paper):
            paper = self._fetch_paper_by_id(paper_id, fields=fields)
            if paper is not None:
                return self._adapt_resolved_paper(paper)

        if target_paper.title:
            paper = self._search_match_by_title(target_paper.title, fields=fields)
            if paper is not None:
                return self._adapt_resolved_paper(paper)

        raise RuntimeError("unable to resolve target paper in Semantic Scholar")

    def fetch_citations(
        self,
        paper_ref: dict[str, object],
        max_results: int = 20,
        *,
        fields: str = DEFAULT_CITATION_FIELDS,
        page_size: int = 100,
    ) -> list[dict[str, object]]:
        paper_id = str(
            paper_ref.get("paper_id")
            or paper_ref.get("source_record_id")
            or paper_ref.get("canonical_id")
            or ""
        ).strip()
        if not paper_id:
            raise RuntimeError("paper_ref is missing paper_id")

        citations: list[dict[str, object]] = []
        offset = 0
        limit = min(max(page_size, 1), max_results or page_size, 1000)

        while len(citations) < max_results:
            batch_size = min(limit, max_results - len(citations))
            payload = self._get_json(
                f"/paper/{parse.quote(paper_id, safe='')}/citations",
                {
                    "fields": fields,
                    "offset": str(offset),
                    "limit": str(batch_size),
                },
            )
            rows = payload.get("data")
            if not isinstance(rows, list) or not rows:
                break

            adapted_rows = [self._adapt_citation_row(row) for row in rows]
            citations.extend(row for row in adapted_rows if row is not None)

            offset += len(rows)
            if len(rows) < batch_size:
                break

        return citations

    def _candidate_identifiers(self, target_paper: TargetPaper) -> Iterable[str]:
        source_ids = target_paper.source_ids or {}

        doi = (target_paper.doi or source_ids.get("doi") or "").strip()
        if doi:
            yield f"DOI:{doi}"

        for key in ("semantic_scholar", "semantic_scholar_paper_id", "paper_id", "paperId"):
            value = str(source_ids.get(key) or "").strip()
            if value:
                yield value

        for key in ("corpus_id", "corpusId"):
            value = str(source_ids.get(key) or "").strip()
            if value:
                yield f"CorpusId:{value}"

        arxiv = str(source_ids.get("arxiv") or source_ids.get("arxiv_id") or "").strip()
        if arxiv:
            yield f"ARXIV:{arxiv}"

        if target_paper.paper_query and target_paper.paper_query_type in {"doi", "paper_id", "arxiv"}:
            query = target_paper.paper_query.strip()
            if query:
                if target_paper.paper_query_type == "doi":
                    yield f"DOI:{query}"
                elif target_paper.paper_query_type == "arxiv":
                    yield f"ARXIV:{query}"
                else:
                    yield query

    def _fetch_paper_by_id(self, paper_id: str, *, fields: str) -> dict[str, Any] | None:
        try:
            payload = self._get_json(
                f"/paper/{parse.quote(paper_id, safe=':')}",
                {"fields": fields},
            )
        except error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise
        return payload if isinstance(payload, dict) and payload.get("paperId") else None

    def _search_match_by_title(self, title: str, *, fields: str) -> dict[str, Any] | None:
        payload = self._get_json(
            "/paper/search/match",
            {
                "query": title,
                "fields": fields,
            },
        )
        return payload if isinstance(payload, dict) and payload.get("paperId") else None

    def _get_json(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{parse.urlencode(params)}"

        headers = {
            "Accept": "application/json",
            "User-Agent": "CiteAnalyzer-Agent/semantic-scholar-client",
        }
        if self._api_key:
            headers["x-api-key"] = self._api_key

        last_error: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            req = request.Request(url, headers=headers, method="GET")
            try:
                with request.urlopen(req, timeout=self._config.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except error.HTTPError as exc:
                last_error = exc
                if not self._should_retry(exc.code, attempt):
                    raise
                self._sleep_before_retry(exc, attempt)
            except (error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt >= self._config.max_retries:
                    raise RuntimeError(f"request failed for {url}: {exc}") from exc
                self._sleep_before_retry(None, attempt)

        raise RuntimeError(f"request failed for {url}: {last_error}")

    def _should_retry(self, status_code: int, attempt: int) -> bool:
        return attempt < self._config.max_retries and (status_code == 429 or status_code >= 500)

    def _sleep_before_retry(self, http_error: error.HTTPError | None, attempt: int) -> None:
        if http_error is not None:
            retry_after = http_error.headers.get("Retry-After")
            if retry_after:
                try:
                    time.sleep(max(float(retry_after), 0.0))
                    return
                except ValueError:
                    pass
        time.sleep(self._config.backoff_seconds * (2 ** attempt))

    def _adapt_resolved_paper(self, paper: dict[str, Any]) -> dict[str, object]:
        external_ids = paper.get("externalIds")
        external_ids = external_ids if isinstance(external_ids, dict) else {}

        paper_id = str(paper.get("paperId") or "").strip()
        doi = self._clean_optional_str(external_ids.get("DOI"))
        title = self._clean_optional_str(paper.get("title"))

        return {
            "paper_id": paper_id,
            "source_name": "semantic_scholar",
            "source_record_id": paper_id,
            "canonical_id": paper_id,
            "title": title,
            "doi": doi,
            "year": self._coerce_int(paper.get("year")),
            "authors": self._extract_author_names(paper.get("authors")),
            "venue": self._clean_optional_str(paper.get("venue")),
            "url": self._clean_optional_str(paper.get("url")),
            "source_specific_ids": {
                "semantic_scholar": paper_id,
                **({"doi": doi} if doi else {}),
            },
            "source_links": {
                "semantic_scholar": self._clean_optional_str(paper.get("url")) or "",
            },
        }

    def _adapt_citation_row(self, row: Any) -> dict[str, object] | None:
        if not isinstance(row, dict):
            return None

        citing_paper = row.get("citingPaper")
        if not isinstance(citing_paper, dict):
            return None

        external_ids = citing_paper.get("externalIds")
        external_ids = external_ids if isinstance(external_ids, dict) else {}

        paper_id = self._clean_optional_str(citing_paper.get("paperId"))
        if not paper_id:
            return None

        doi = self._clean_optional_str(external_ids.get("DOI"))
        url = self._clean_optional_str(citing_paper.get("url"))

        return {
            "source_name": "semantic_scholar",
            "source_record_id": paper_id,
            "title": self._clean_optional_str(citing_paper.get("title")) or "",
            "doi": doi,
            "year": self._coerce_int(citing_paper.get("year")),
            "authors": self._extract_author_names(citing_paper.get("authors")),
            "venue": self._clean_optional_str(citing_paper.get("venue")),
            "abstract": self._clean_optional_str(citing_paper.get("abstract")),
            "url": url,
            "source_names": ["semantic_scholar"],
            "source_specific_ids": {
                "semantic_scholar": paper_id,
                **({"doi": doi} if doi else {}),
            },
            "source_links": {
                "semantic_scholar": url or "",
            },
        }

    def _extract_author_names(self, authors: Any) -> list[str]:
        if not isinstance(authors, list):
            return []

        names: list[str] = []
        for author in authors:
            if isinstance(author, dict):
                name = self._clean_optional_str(author.get("name"))
            else:
                name = self._clean_optional_str(author)
            if name:
                names.append(name)
        return names

    def _coerce_int(self, value: Any) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return int(value)
            except ValueError:
                return None
        return None

    def _clean_optional_str(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
