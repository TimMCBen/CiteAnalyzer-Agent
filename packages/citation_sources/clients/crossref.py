from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


@dataclass(frozen=True)
class _RequestConfig:
    timeout_seconds: float = 10.0
    max_retries: int = 3
    backoff_base_seconds: float = 0.5
    backoff_max_seconds: float = 8.0


class CrossrefClient:
    """Thin metadata-oriented client for the Crossref REST API."""

    BASE_URL = "https://api.crossref.org/v1"
    SELECT_FIELDS = ",".join(
        [
            "DOI",
            "URL",
            "title",
            "author",
            "published-print",
            "published-online",
            "issued",
            "container-title",
            "short-container-title",
            "abstract",
            "is-referenced-by-count",
            "type",
        ]
    )

    def __init__(
        self,
        *,
        mailto: str | None = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        backoff_base_seconds: float = 0.5,
        backoff_max_seconds: float = 8.0,
        user_agent: str | None = None,
    ) -> None:
        self._mailto = (mailto or os.getenv("CROSSREF_MAILTO") or "").strip() or None
        self._config = _RequestConfig(
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            backoff_base_seconds=backoff_base_seconds,
            backoff_max_seconds=backoff_max_seconds,
        )
        self._user_agent = user_agent or "CiteAnalyzer-Agent/0.1 (+https://api.crossref.org/)"

    def fetch_work_by_doi(self, doi: str) -> dict[str, Any] | None:
        normalized_doi = self._normalize_doi(doi)
        if not normalized_doi:
            return None

        payload = self._request_json(f"/works/{parse.quote(normalized_doi, safe='')}")
        message = payload.get("message")
        if not isinstance(message, dict):
            return None
        return self._normalize_work(message)

    def search_work_match(
        self,
        title: str,
        year: int | None = None,
        authors: list[str] | None = None,
    ) -> dict[str, Any] | None:
        clean_title = str(title or "").strip()
        if not clean_title:
            return None

        bibliographic_parts = [clean_title]
        if authors:
            bibliographic_parts.extend(author.strip() for author in authors if author and author.strip())
        if year is not None:
            bibliographic_parts.append(str(year))

        params = {
            "query.title": clean_title,
            "query.bibliographic": " ".join(bibliographic_parts),
            "rows": "5",
            "select": self.SELECT_FIELDS,
        }

        payload = self._request_json("/works", params=params)
        message = payload.get("message")
        if not isinstance(message, dict):
            return None

        items = message.get("items")
        if not isinstance(items, list):
            return None

        candidates = [
            normalized
            for item in items
            if isinstance(item, dict)
            for normalized in [self._normalize_work(item)]
            if normalized.get("title")
        ]
        if not candidates:
            return None

        best_match = max(candidates, key=lambda item: self._score_match(item, clean_title, year, authors))
        if self._score_match(best_match, clean_title, year, authors) <= 0:
            return None
        return best_match

    def enrich_candidate(self, candidate: dict[str, object]) -> dict[str, object]:
        enriched = dict(candidate)
        source_names = [str(name) for name in enriched.get("source_names", []) if isinstance(name, str)]
        source_links = {
            str(key): str(value)
            for key, value in dict(enriched.get("source_links") or {}).items()
            if isinstance(key, str) and isinstance(value, str)
        }
        source_specific_ids = {
            str(key): str(value)
            for key, value in dict(enriched.get("source_specific_ids") or {}).items()
            if isinstance(key, str) and isinstance(value, str)
        }

        doi = enriched.get("doi") if isinstance(enriched.get("doi"), str) else None
        title = enriched.get("title") if isinstance(enriched.get("title"), str) else ""
        year = enriched.get("year") if isinstance(enriched.get("year"), int) else None
        authors = [author for author in list(enriched.get("authors") or []) if isinstance(author, str)]

        match = self.fetch_work_by_doi(doi) if doi else None
        if match is None:
            match = self.search_work_match(title=title, year=year, authors=authors)
        if match is None:
            return enriched

        enriched["title"] = enriched.get("title") or match.get("title") or ""
        enriched["doi"] = enriched.get("doi") or match.get("doi")
        if enriched.get("year") is None and match.get("year") is not None:
            enriched["year"] = match["year"]
        if not enriched.get("authors") and match.get("authors"):
            enriched["authors"] = list(match["authors"])
        if not enriched.get("venue") and match.get("venue"):
            enriched["venue"] = match["venue"]
        if not enriched.get("abstract") and match.get("abstract"):
            enriched["abstract"] = match["abstract"]
        if not enriched.get("url") and match.get("url"):
            enriched["url"] = match["url"]

        source_specific_ids["crossref"] = str(match.get("source_record_id") or match.get("doi") or "")
        if match.get("url"):
            source_links["crossref"] = str(match["url"])
        if "crossref" not in source_names:
            source_names.append("crossref")

        if enriched.get("source_name") == "crossref":
            enriched["source_record_id"] = match.get("source_record_id") or enriched.get("source_record_id") or ""
        elif not enriched.get("source_record_id"):
            enriched["source_record_id"] = str(match.get("source_record_id") or "")

        enriched["source_names"] = source_names
        enriched["source_links"] = source_links
        enriched["source_specific_ids"] = source_specific_ids
        enriched["crossref"] = match
        return enriched

    def _request_json(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        query_params = dict(params or {})
        if self._mailto:
            query_params["mailto"] = self._mailto

        url = f"{self.BASE_URL}{path}"
        if query_params:
            url = f"{url}?{parse.urlencode(query_params)}"

        headers = {
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }
        request_obj = request.Request(url, headers=headers, method="GET")

        attempts = 0
        while True:
            attempts += 1
            try:
                with request.urlopen(request_obj, timeout=self._config.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except error.HTTPError as exc:
                if exc.code == 404:
                    return {}
                if not self._should_retry(exc.code, attempts):
                    raise RuntimeError(f"crossref request failed with status {exc.code}") from exc
                self._sleep_before_retry(exc.headers.get("Retry-After"), attempts)
            except error.URLError as exc:
                if attempts > self._config.max_retries:
                    raise RuntimeError(f"crossref request failed: {exc.reason}") from exc
                self._sleep_before_retry(None, attempts)

    def _sleep_before_retry(self, retry_after: str | None, attempts: int) -> None:
        if retry_after:
            try:
                delay_seconds = float(retry_after)
            except ValueError:
                delay_seconds = self._compute_backoff_delay(attempts)
        else:
            delay_seconds = self._compute_backoff_delay(attempts)
        time.sleep(delay_seconds)

    def _compute_backoff_delay(self, attempts: int) -> float:
        exponential = self._config.backoff_base_seconds * (2 ** max(attempts - 1, 0))
        capped = min(exponential, self._config.backoff_max_seconds)
        return capped + random.uniform(0.0, 0.25)

    def _should_retry(self, status_code: int, attempts: int) -> bool:
        if attempts > self._config.max_retries:
            return False
        return status_code == 429 or 500 <= status_code < 600

    def _normalize_work(self, work: dict[str, Any]) -> dict[str, Any]:
        doi = self._normalize_doi(work.get("DOI"))
        title = self._pick_first_text(work.get("title"))
        venue = self._pick_first_text(work.get("container-title")) or self._pick_first_text(
            work.get("short-container-title")
        )
        return {
            "source_name": "crossref",
            "source_record_id": doi or "",
            "title": title,
            "doi": doi,
            "year": self._extract_year(work),
            "authors": self._extract_authors(work.get("author")),
            "venue": venue,
            "abstract": self._normalize_abstract(work.get("abstract")),
            "url": str(work.get("URL") or "").strip(),
            "citation_count": self._coerce_int(work.get("is-referenced-by-count")),
            "work_type": str(work.get("type") or "").strip() or None,
        }

    def _score_match(
        self,
        work: dict[str, Any],
        title: str,
        year: int | None,
        authors: list[str] | None,
    ) -> float:
        score = 0.0
        normalized_input_title = self._normalize_text(title)
        normalized_work_title = self._normalize_text(work.get("title"))

        if normalized_input_title and normalized_work_title:
            if normalized_input_title == normalized_work_title:
                score += 10.0
            elif normalized_input_title in normalized_work_title or normalized_work_title in normalized_input_title:
                score += 7.0
            else:
                input_tokens = set(normalized_input_title.split())
                work_tokens = set(normalized_work_title.split())
                if input_tokens and work_tokens:
                    overlap = len(input_tokens & work_tokens) / max(len(input_tokens), len(work_tokens))
                    score += overlap * 5.0

        work_year = work.get("year") if isinstance(work.get("year"), int) else None
        if year is not None and work_year is not None:
            if year == work_year:
                score += 3.0
            elif abs(year - work_year) == 1:
                score += 1.0

        if authors:
            normalized_authors = [self._normalize_text(author) for author in authors if author]
            work_authors = [self._normalize_text(author) for author in work.get("authors", []) if isinstance(author, str)]
            if normalized_authors and work_authors:
                author_overlap = len(set(normalized_authors) & set(work_authors))
                score += min(author_overlap, 2) * 2.0

        if work.get("doi"):
            score += 0.5

        return score

    @staticmethod
    def _extract_authors(raw_authors: Any) -> list[str]:
        if not isinstance(raw_authors, list):
            return []

        authors: list[str] = []
        for author in raw_authors:
            if not isinstance(author, dict):
                continue
            given = str(author.get("given") or "").strip()
            family = str(author.get("family") or "").strip()
            literal = str(author.get("literal") or "").strip()
            full_name = " ".join(part for part in [given, family] if part).strip() or literal
            if full_name:
                authors.append(full_name)
        return authors

    @staticmethod
    def _extract_year(work: dict[str, Any]) -> int | None:
        for key in ("published-print", "published-online", "issued"):
            date_parts = work.get(key)
            if not isinstance(date_parts, dict):
                continue
            parts = date_parts.get("date-parts")
            if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
                year = parts[0][0]
                if isinstance(year, int):
                    return year
        return None

    @staticmethod
    def _pick_first_text(value: Any) -> str:
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    return item.strip()
            return ""
        if isinstance(value, str):
            return value.strip()
        return ""

    @staticmethod
    def _normalize_abstract(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        text = value.strip()
        return text or None

    @staticmethod
    def _normalize_doi(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        doi = value.strip().lower()
        if doi.startswith("https://doi.org/"):
            doi = doi.removeprefix("https://doi.org/")
        elif doi.startswith("http://doi.org/"):
            doi = doi.removeprefix("http://doi.org/")
        elif doi.startswith("doi:"):
            doi = doi.removeprefix("doi:")
        return doi or None

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if not isinstance(value, str):
            return ""
        collapsed = " ".join(value.casefold().split())
        cleaned = "".join(ch for ch in collapsed if ch.isalnum() or ch.isspace())
        return " ".join(cleaned.split())

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        return value if isinstance(value, int) else None
