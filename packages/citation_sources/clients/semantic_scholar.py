"""Client helpers for Semantic Scholar operations in citation source collection."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Iterable
from urllib import error, parse, request

from packages.shared.models import TargetPaper
from packages.shared.runtime_logging import get_runtime_logger


DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 1.0
DEFAULT_RESOLVE_FIELDS = (
    "paperId,title,externalIds,year,venue,url,authors"
)
DEFAULT_CITATION_FIELDS = (
    "citingPaper.paperId,citingPaper.title,citingPaper.externalIds,"
    "citingPaper.year,citingPaper.venue,citingPaper.url,citingPaper.authors"
)


@dataclass(frozen=True)
class _RequestConfig:
    """Store request config information used by citation source collection."""
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS


class SemanticScholarClient:
    """Thin Graph API client for stage2 citation fetching."""

    default_base_url = "https://api.semanticscholar.org/graph/v1"

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
        self._api_key = (api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY") or "").strip() or None
        self._base_url = (
            os.getenv("SEMANTIC_SCHOLAR_BASE_URL") or self.default_base_url
        ).rstrip("/")
        self._auth_mode = (
            os.getenv("SEMANTIC_SCHOLAR_AUTH_MODE") or "x-api-key"
        ).strip().lower()
        self._last_request_at = 0.0

    def resolve_target_paper(
        self,
        target_paper: TargetPaper,
        *,
        fields: str = DEFAULT_RESOLVE_FIELDS,
    ) -> dict[str, object]:
        """Resolve target paper for Semantic Scholar client."""
        title_fallback = target_paper.title or (
            target_paper.paper_query if target_paper.paper_query_type == "title" else None
        )

        for paper_id in self._candidate_identifiers(target_paper):
            try:
                paper = self._fetch_paper_by_id(paper_id, fields=fields)
            except Exception:
                paper = None
            if paper is not None:
                return self._adapt_resolved_paper(paper)

        if title_fallback:
            paper = self._search_match_by_title(title_fallback, fields=fields)
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
        """Fetch citations for Semantic Scholar client."""
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
        """Build Semantic Scholar candidate identifiers for a target paper for Semantic Scholar client."""
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

        arxiv = _normalize_arxiv_id(str(source_ids.get("arxiv") or source_ids.get("arxiv_id") or "").strip())
        if arxiv:
            yield f"ARXIV:{arxiv}"

        if target_paper.paper_query and target_paper.paper_query_type in {"doi", "paper_id", "arxiv"}:
            query = target_paper.paper_query.strip()
            if query:
                if target_paper.paper_query_type == "doi":
                    yield f"DOI:{query}"
                elif target_paper.paper_query_type == "arxiv":
                    normalized_arxiv = _normalize_arxiv_id(query)
                    if normalized_arxiv:
                        yield f"ARXIV:{normalized_arxiv}"
                else:
                    yield query

    def _fetch_paper_by_id(self, paper_id: str, *, fields: str) -> dict[str, Any] | None:
        """Fetch paper by id for Semantic Scholar client."""
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
        """Search match by title for Semantic Scholar client."""
        payload = self._get_json(
            "/paper/search/match",
            {
                "query": title,
                "fields": fields,
            },
        )
        return payload if isinstance(payload, dict) and payload.get("paperId") else None

    def _get_json(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        """Return JSON for Semantic Scholar client."""
        url = f"{self._base_url}{path}"
        if params:
            url = f"{url}?{parse.urlencode(params)}"

        headers = {
            "Accept": "application/json",
            "User-Agent": "CiteAnalyzer-Agent/semantic-scholar-client",
        }
        if self._api_key:
            if self._auth_mode == "bearer":
                headers["Authorization"] = f"Bearer {self._api_key}"
            else:
                headers["x-api-key"] = self._api_key

        last_error: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            req = request.Request(url, headers=headers, method="GET")
            try:
                self._respect_rate_limit(path)
                get_runtime_logger().detail(
                    "semantic_scholar.request",
                    "正在请求 Semantic Scholar",
                    path=path,
                    attempt=attempt + 1,
                )
                with request.urlopen(req, timeout=self._config.timeout_seconds) as response:
                    get_runtime_logger().detail(
                        "semantic_scholar.response",
                        "Semantic Scholar 请求成功",
                        path=path,
                        status=response.status,
                    )
                    return json.loads(response.read().decode("utf-8"))
            except error.HTTPError as exc:
                last_error = exc
                if not self._should_retry(exc.code, attempt):
                    get_runtime_logger().warn(
                        "semantic_scholar.request",
                        "Semantic Scholar 请求失败，当前错误不可重试",
                        path=path,
                        status=exc.code,
                    )
                    raise
                self._sleep_before_retry(exc, attempt)
            except (error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt >= self._config.max_retries:
                    get_runtime_logger().warn(
                        "semantic_scholar.request",
                        "Semantic Scholar 请求多次失败，已达到重试上限",
                        path=path,
                        error_type=exc.__class__.__name__,
                    )
                    raise RuntimeError(f"request failed for {url}: {exc}") from exc
                self._sleep_before_retry(None, attempt)

        raise RuntimeError(f"request failed for {url}: {last_error}")

    def _should_retry(self, status_code: int, attempt: int) -> bool:
        return attempt < self._config.max_retries and (status_code == 429 or status_code >= 500)

    def _sleep_before_retry(self, http_error: error.HTTPError | None, attempt: int) -> None:
        """Wait before retrying transient API failures for Semantic Scholar client."""
        if http_error is not None:
            retry_after = http_error.headers.get("Retry-After")
            if retry_after:
                try:
                    delay = max(float(retry_after), 0.0)
                    get_runtime_logger().detail(
                        "semantic_scholar.rate_limit",
                        "Semantic Scholar 要求等待后重试",
                        seconds=f"{delay:.2f}",
                    )
                    time.sleep(delay)
                    return
                except ValueError:
                    pass
        delay = self._config.backoff_seconds * (2 ** attempt)
        get_runtime_logger().detail(
            "semantic_scholar.retry",
            "Semantic Scholar 请求将重试",
            seconds=f"{delay:.2f}",
        )
        time.sleep(delay)

    def _respect_rate_limit(self, path: str) -> None:
        """Throttle requests to respect upstream rate limits for Semantic Scholar client."""
        if self._config.backoff_seconds <= 0:
            return
        now = time.monotonic()
        elapsed = now - self._last_request_at
        if self._last_request_at and elapsed < self._config.backoff_seconds:
            delay = self._config.backoff_seconds - elapsed
            get_runtime_logger().detail(
                "semantic_scholar.rate_limit",
                "等待以遵守 Semantic Scholar 每秒最多 1 次请求限制",
                path=path,
                seconds=f"{delay:.2f}",
            )
            time.sleep(delay)
        self._last_request_at = time.monotonic()

    def _adapt_resolved_paper(self, paper: dict[str, Any]) -> dict[str, object]:
        """Convert resolved Semantic Scholar metadata into a target paper for Semantic Scholar client."""
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
        """Convert Semantic Scholar citation rows into normalized candidates for Semantic Scholar client."""
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
            "abstract": None,
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
        """Extract author names for Semantic Scholar client."""
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
        """Coerce numeric API fields into integers for Semantic Scholar client."""
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return int(value)
            except ValueError:
                return None
        return None

    def _clean_optional_str(self, value: Any) -> str | None:
        """Normalize optional string fields from API payloads for Semantic Scholar client."""
        if value is None:
            return None
        text = str(value).strip()
        return text or None


def _normalize_arxiv_id(value: str) -> str | None:
    """Normalize arXiv id for citation source collection."""
    text = value.strip()
    if not text:
        return None
    match = parse.unquote(text)
    for prefix in ("ARXIV:", "arxiv:"):
        if match.startswith(prefix):
            match = match[len(prefix):]
    import re

    found = re.search(r"(?P<identifier>\d{4}\.\d{4,5})(?:v\d+)?", match, re.IGNORECASE)
    if not found:
        return None
    return found.group("identifier")
