"""Configurable web-search clients used as optional metadata fallbacks."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

from packages.shared.network_retry import RetryPolicy, retry_call
from packages.shared.runtime_logging import get_runtime_logger


@dataclass(frozen=True)
class WebSearchResult:
    """Store one normalized web-search result for LLM verification."""
    title: str
    url: str
    snippet: str = ""
    source: str = "web_search"


class WebSearchUnavailable(RuntimeError):
    """Raised when no supported web-search provider has been configured."""


class GenericWebSearchClient:
    """Search the web through a configured external search API provider."""

    def __init__(
        self,
        *,
        provider: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 15.0,
        max_attempts: int = 2,
    ) -> None:
        self.provider = (provider or os.getenv("WEB_SEARCH_PROVIDER") or "").strip().lower()
        self.api_key = (api_key or self._api_key_for_provider(self.provider) or "").strip()
        self.timeout_seconds = timeout_seconds
        self._retry_policy = RetryPolicy(
            service="WebSearch",
            operation="搜索查询",
            max_attempts=max_attempts,
            base_delay_seconds=0.5,
            max_delay_seconds=2.0,
            jitter_seconds=0.2,
            overall_budget_seconds=6.0,
            impact="stage1_metadata_fallback",
        )

    @classmethod
    def from_env(cls) -> "GenericWebSearchClient":
        """Build a search client by auto-detecting configured provider credentials."""
        provider = (os.getenv("WEB_SEARCH_PROVIDER") or "").strip().lower()
        if not provider:
            for candidate, env_name in (
                ("tavily", "TAVILY_API_KEY"),
                ("brave", "BRAVE_SEARCH_API_KEY"),
                ("serpapi", "SERPAPI_API_KEY"),
            ):
                if os.getenv(env_name):
                    provider = candidate
                    break
        return cls(provider=provider)

    def is_configured(self) -> bool:
        """Return whether this client can call a supported provider."""
        return self.provider in {"tavily", "brave", "serpapi"} and bool(self.api_key)

    def search(self, query: str, *, max_results: int = 5) -> list[WebSearchResult]:
        """Search the configured provider and return normalized result rows."""
        clean_query = str(query or "").strip()
        if not clean_query:
            return []
        if not self.is_configured():
            raise WebSearchUnavailable(
                "Set WEB_SEARCH_PROVIDER=tavily|brave|serpapi and the matching API key "
                "(TAVILY_API_KEY, BRAVE_SEARCH_API_KEY, or SERPAPI_API_KEY)."
            )
        get_runtime_logger().detail(
            "web_search.request",
            "正在请求通用搜索 API",
            provider=self.provider,
            query=clean_query,
            max_results=max_results,
        )
        return retry_call(lambda: self._search_once(clean_query, max_results=max_results), self._retry_policy)

    def _search_once(self, query: str, *, max_results: int) -> list[WebSearchResult]:
        """Dispatch one search request to the selected provider adapter."""
        if self.provider == "tavily":
            return self._search_tavily(query, max_results=max_results)
        if self.provider == "brave":
            return self._search_brave(query, max_results=max_results)
        if self.provider == "serpapi":
            return self._search_serpapi(query, max_results=max_results)
        raise WebSearchUnavailable(f"Unsupported WEB_SEARCH_PROVIDER: {self.provider}")

    def _search_tavily(self, query: str, *, max_results: int) -> list[WebSearchResult]:
        """Call Tavily search and normalize its result rows."""
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "query": query,
                "max_results": max(1, min(max_results, 10)),
                "search_depth": "basic",
                "include_answer": False,
            },
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "CiteAnalyzer-Agent/web-search",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return [
            WebSearchResult(
                title=_clean_str(item.get("title")),
                url=_clean_str(item.get("url")),
                snippet=_clean_str(item.get("content")),
                source="tavily",
            )
            for item in _list(payload.get("results"))
            if _clean_str(item.get("title")) and _clean_str(item.get("url"))
        ][:max_results]

    def _search_brave(self, query: str, *, max_results: int) -> list[WebSearchResult]:
        """Call Brave Search and normalize its web result rows."""
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max(1, min(max_results, 20))},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
                "User-Agent": "CiteAnalyzer-Agent/web-search",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        web = payload.get("web") if isinstance(payload.get("web"), dict) else {}
        return [
            WebSearchResult(
                title=_clean_str(item.get("title")),
                url=_clean_str(item.get("url")),
                snippet=_clean_str(item.get("description")),
                source="brave",
            )
            for item in _list(web.get("results"))
            if _clean_str(item.get("title")) and _clean_str(item.get("url"))
        ][:max_results]

    def _search_serpapi(self, query: str, *, max_results: int) -> list[WebSearchResult]:
        """Call SerpAPI Google search and normalize organic result rows."""
        response = requests.get(
            "https://serpapi.com/search.json",
            params={"q": query, "api_key": self.api_key, "engine": "google", "num": max(1, min(max_results, 10))},
            headers={"User-Agent": "CiteAnalyzer-Agent/web-search"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return [
            WebSearchResult(
                title=_clean_str(item.get("title")),
                url=_clean_str(item.get("link")),
                snippet=_clean_str(item.get("snippet")),
                source="serpapi",
            )
            for item in _list(payload.get("organic_results"))
            if _clean_str(item.get("title")) and _clean_str(item.get("link"))
        ][:max_results]

    @staticmethod
    def _api_key_for_provider(provider: str) -> str:
        """Read the provider-specific API key from supported environment names."""
        if provider == "tavily":
            return os.getenv("TAVILY_API_KEY") or os.getenv("WEB_SEARCH_API_KEY") or ""
        if provider == "brave":
            return os.getenv("BRAVE_SEARCH_API_KEY") or os.getenv("WEB_SEARCH_API_KEY") or ""
        if provider == "serpapi":
            return os.getenv("SERPAPI_API_KEY") or os.getenv("WEB_SEARCH_API_KEY") or ""
        return ""


def _clean_str(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
