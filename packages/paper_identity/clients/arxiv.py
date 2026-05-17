from __future__ import annotations

import re
import time
from typing import Callable
from urllib.parse import quote, urlencode
from xml.etree import ElementTree

import requests

from packages.paper_identity.models import CandidateAuthor, CandidateWork
from packages.paper_identity.title_similarity import normalize_title_for_match
from packages.shared.network_retry import RetryPolicy, retry_call
from packages.shared.runtime_logging import get_runtime_logger


ARXIV_API_BASE_URL = "http://export.arxiv.org/api/query"
ARXIV_ABS_PATTERN = re.compile(r"(?:arxiv\.org/(?:abs|pdf|html)/|10\.48550/arxiv\.)(?P<id>\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)
PLAIN_ARXIV_ID_PATTERN = re.compile(r"(?P<id>\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)


class ArxivMetadataClient:
    def __init__(
        self,
        *,
        min_interval_seconds: float = 3.1,
        timeout_seconds: float = 20.0,
        fetcher: Callable[[str], str] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._min_interval_seconds = max(min_interval_seconds, 0.0)
        self._timeout_seconds = timeout_seconds
        self._fetcher = fetcher
        self._sleeper = sleeper
        self._monotonic = monotonic
        self._last_request_at = 0.0
        self._id_cache: dict[str, CandidateWork | None] = {}
        self._title_cache: dict[str, list[CandidateWork]] = {}
        self.request_count = 0
        self.http_attempt_count = 0
        self.cache_hits = 0

    def lookup_ids(self, arxiv_ids: list[str]) -> list[CandidateWork]:
        normalized_ids = []
        for value in arxiv_ids:
            arxiv_id = normalize_arxiv_id(value)
            if arxiv_id and arxiv_id not in normalized_ids:
                normalized_ids.append(arxiv_id)
        if not normalized_ids:
            return []

        missing = [arxiv_id for arxiv_id in normalized_ids if arxiv_id not in self._id_cache]
        if missing:
            url = f"{ARXIV_API_BASE_URL}?{urlencode({'id_list': ','.join(missing)})}"
            payload = self._get_text(url)
            works = _parse_arxiv_atom(payload)
            by_id = {work.arxiv_id: work for work in works if work.arxiv_id}
            for arxiv_id in missing:
                self._id_cache[arxiv_id] = by_id.get(arxiv_id)

        results = []
        for arxiv_id in normalized_ids:
            cached = self._id_cache.get(arxiv_id)
            if cached is not None:
                self.cache_hits += 1
                results.append(cached)
        return results

    def search_by_title(self, title: str, *, max_results: int = 3) -> list[CandidateWork]:
        normalized_title = normalize_title_for_match(title)
        if not normalized_title:
            return []
        if normalized_title in self._title_cache:
            self.cache_hits += 1
            get_runtime_logger().detail("arxiv.cache_hit", "arXiv 标题搜索命中缓存", title=title)
            return list(self._title_cache[normalized_title])

        query = f'ti:"{title.strip()}"'
        url = f"{ARXIV_API_BASE_URL}?{urlencode({'search_query': query, 'start': '0', 'max_results': str(max_results)})}"
        payload = self._get_text(url)
        works = _parse_arxiv_atom(payload)

        self._title_cache[normalized_title] = works
        if works:
            get_runtime_logger().detail("arxiv.cache_miss", "arXiv 标题搜索完成并写入正缓存", title=title, count=len(works))
        else:
            get_runtime_logger().detail("arxiv.cache_miss", "arXiv 标题搜索无结果并写入负缓存", title=title)
        return list(works)

    def _get_text(self, url: str) -> str:
        self._respect_rate_limit()
        policy = RetryPolicy(
            service="arXiv",
            operation="论文身份元数据查询",
            max_attempts=2,
            base_delay_seconds=0.5,
            max_delay_seconds=2.0,
            jitter_seconds=0.1,
            overall_budget_seconds=8.0,
            impact="single_identity_lookup",
        )
        return retry_call(lambda: self._fetch_text_once(url), policy)

    def _fetch_text_once(self, url: str) -> str:
        self.request_count += 1
        self.http_attempt_count += 1
        if self._fetcher is not None:
            return self._fetcher(url)
        response = requests.get(url, timeout=self._timeout_seconds, headers={"User-Agent": "CiteAnalyzer-Agent/paper-identity-arxiv"})
        response.raise_for_status()
        return response.text

    def _respect_rate_limit(self) -> None:
        now = self._monotonic()
        elapsed = now - self._last_request_at
        if self._last_request_at and elapsed < self._min_interval_seconds:
            delay = self._min_interval_seconds - elapsed
            get_runtime_logger().detail(
                "arxiv.throttle_wait",
                "等待以遵守 arXiv API 限速",
                seconds=f"{delay:.2f}",
            )
            self._sleeper(delay)
        self._last_request_at = self._monotonic()


def normalize_arxiv_id(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    for pattern in (ARXIV_ABS_PATTERN, PLAIN_ARXIV_ID_PATTERN):
        match = pattern.search(text)
        if match:
            return re.sub(r"v\d+$", "", match.group("id"), flags=re.IGNORECASE)
    return None


def extract_arxiv_ids_from_links(values: list[str]) -> list[str]:
    found: list[str] = []
    for value in values:
        arxiv_id = normalize_arxiv_id(value)
        if arxiv_id and arxiv_id not in found:
            found.append(arxiv_id)
    return found


def arxiv_candidate_urls(work: CandidateWork) -> list[str]:
    if not work.arxiv_id:
        return []
    return [
        f"https://arxiv.org/pdf/{quote(work.arxiv_id)}.pdf",
        f"https://arxiv.org/html/{quote(work.arxiv_id)}",
        f"https://arxiv.org/abs/{quote(work.arxiv_id)}",
    ]


def _parse_arxiv_atom(payload: str) -> list[CandidateWork]:
    root = ElementTree.fromstring(payload)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    works: list[CandidateWork] = []
    for entry in root.findall("atom:entry", namespace):
        title = " ".join((entry.findtext("atom:title", default="", namespaces=namespace) or "").split())
        entry_id = (entry.findtext("atom:id", default="", namespaces=namespace) or "").strip()
        arxiv_id = normalize_arxiv_id(entry_id)
        if not title or not arxiv_id:
            continue
        authors = [
            CandidateAuthor(name=" ".join((author.findtext("atom:name", default="", namespaces=namespace) or "").split()))
            for author in entry.findall("atom:author", namespace)
        ]
        authors = [author for author in authors if author.name]
        works.append(
            CandidateWork(
                source="arxiv",
                work_id=entry_id or f"https://arxiv.org/abs/{arxiv_id}",
                title=title,
                doi=f"10.48550/arXiv.{arxiv_id}",
                url=f"https://arxiv.org/abs/{arxiv_id}",
                pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
                arxiv_id=arxiv_id,
                authors=authors,
                work_type="preprint",
            )
        )
    return works
