"""Target-paper resolution helpers for DOI, arXiv, OpenAlex, and title queries."""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import quote
from xml.etree import ElementTree

import requests

try:
    from pydantic import BaseModel, Field
except ImportError:
    class BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    def Field(default=None, **kwargs):  # type: ignore
        return default

from packages.citation_sources.clients.semantic_scholar import SemanticScholarClient
from packages.shared.models import TargetPaper
from packages.shared.network_retry import RetryExhaustedError, RetryPolicy, retry_call
from packages.shared.runtime_logging import get_runtime_logger
from packages.shared.web_search import GenericWebSearchClient, WebSearchResult, WebSearchUnavailable

REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "CiteAnalyzer-Agent/0.1"
DOI_RESOLVE_RETRY = RetryPolicy(
    service="Crossref",
    operation="DOI解析",
    max_attempts=3,
    base_delay_seconds=0.5,
    max_delay_seconds=4.0,
    jitter_seconds=0.2,
)
TITLE_RESOLVE_RETRY = RetryPolicy(
    service="Crossref",
    operation="标题解析",
    max_attempts=2,
    base_delay_seconds=0.5,
    max_delay_seconds=2.0,
    jitter_seconds=0.2,
)
ARXIV_RESOLVE_RETRY = RetryPolicy(
    service="arXiv",
    operation="目标论文解析",
    max_attempts=2,
    base_delay_seconds=0.5,
    max_delay_seconds=1.5,
    jitter_seconds=0.1,
)
ARXIV_TITLE_RETRY = RetryPolicy(
    service="arXiv",
    operation="标题搜索",
    max_attempts=2,
    base_delay_seconds=0.5,
    max_delay_seconds=1.5,
    jitter_seconds=0.1,
)


class WebTitleResolutionModel(BaseModel):
    """Validate LLM selection of a target-paper title from web-search results."""
    title: str = Field(description="Exact English paper title, or UNKNOWN.")
    confidence: str = Field(description="high, medium, low, or unknown")
    source_url: str = Field(description="URL of the search result that supports the title, or empty string.")
    evidence_zh: str = Field(description="中文说明为什么这个标题可信，或为什么无法判断。")


def resolve_target_paper_metadata(target_paper: TargetPaper) -> TargetPaper:
    """Choose the resolver path that can turn a user clue into target metadata."""
    query_type = target_paper.paper_query_type
    get_runtime_logger().detail(
        "resolver.start",
        "开始解析目标论文",
        query_type=query_type,
        query=target_paper.paper_query or target_paper.doi,
    )
    if query_type == "doi" and target_paper.doi:
        return resolve_by_doi(target_paper)
    if query_type == "arxiv" and target_paper.paper_query:
        return resolve_by_arxiv(target_paper)
    if query_type == "paper_id":
        return mark_unresolved(
            target_paper,
            reason="paper_id resolution is not implemented yet",
        )
    if query_type == "title" and target_paper.paper_query:
        return resolve_by_title(target_paper)
    return mark_unresolved(target_paper, reason="missing resolvable paper clue")


def resolve_by_doi(target_paper: TargetPaper) -> TargetPaper:
    """Resolve a DOI through Crossref and return a canonical target-paper record."""
    doi = target_paper.doi or ""
    get_runtime_logger().detail("resolver.crossref", "正在通过 Crossref 解析 DOI", doi=doi)
    response = _get_with_retry(
        f"https://api.crossref.org/works/{doi}",
        DOI_RESOLVE_RETRY,
    )
    message = response.json()["message"]
    title = first_title(message.get("title"))
    if not title:
        get_runtime_logger().warn("resolver.crossref", "Crossref 返回结果缺少标题", doi=doi)
        return mark_unresolved(target_paper, reason="crossref returned no title for doi")

    get_runtime_logger().detail("resolver.crossref", "Crossref 成功解析 DOI", doi=doi, title=title)
    return TargetPaper(
        canonical_id=(message.get("DOI") or doi).lower(),
        paper_query=target_paper.paper_query,
        paper_query_type=target_paper.paper_query_type,
        title=title,
        doi=(message.get("DOI") or doi).lower(),
        source_ids={"doi": (message.get("DOI") or doi).lower(), "crossref": (message.get("DOI") or doi).lower()},
        resolve_status="resolved",
    )


def resolve_by_arxiv(target_paper: TargetPaper) -> TargetPaper:
    """Resolve an arXiv identifier into title, DOI, and source identifiers."""
    arxiv_id = normalize_arxiv_id(target_paper.paper_query or "")
    if not arxiv_id:
        get_runtime_logger().warn("resolver.arxiv", "arXiv 标识格式无效", query=target_paper.paper_query)
        return mark_unresolved(target_paper, reason="invalid arxiv identifier")

    get_runtime_logger().detail("resolver.arxiv", "正在通过 arXiv 解析目标论文", arxiv_id=arxiv_id)
    try:
        response = _get_with_retry(
            f"http://export.arxiv.org/api/query?id_list={quote(arxiv_id)}",
            ARXIV_RESOLVE_RETRY,
        )
    except RetryExhaustedError as exc:
        if exc.status == 429:
            get_runtime_logger().warn(
                "resolver.arxiv",
                "arXiv 元数据接口限流，尝试用外部来源补全标题",
                arxiv_id=arxiv_id,
            )
            return _resolve_arxiv_metadata_fallback(target_paper, arxiv_id, reason="arxiv_429")
        get_runtime_logger().warn(
            "resolver.arxiv",
            "arXiv 元数据接口多次连接失败，尝试用外部来源补全标题",
            arxiv_id=arxiv_id,
            error_type=exc.reason,
        )
        return _resolve_arxiv_metadata_fallback(target_paper, arxiv_id, reason=f"arxiv_retry_exhausted:{exc.reason}")
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 429:
            get_runtime_logger().warn(
                "resolver.arxiv",
                "arXiv 元数据接口限流，尝试用外部来源补全标题",
                arxiv_id=arxiv_id,
            )
            return _resolve_arxiv_metadata_fallback(target_paper, arxiv_id, reason="arxiv_http_429")
        raise
    except requests.RequestException as exc:
        get_runtime_logger().warn(
            "resolver.arxiv",
            "arXiv 元数据接口连接失败，尝试用外部来源补全标题",
            arxiv_id=arxiv_id,
            error_type=exc.__class__.__name__,
        )
        return _resolve_arxiv_metadata_fallback(target_paper, arxiv_id, reason=f"arxiv_request:{exc.__class__.__name__}")
    root = ElementTree.fromstring(response.text)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    arxiv_namespace = {"arxiv": "http://arxiv.org/schemas/atom"}
    entry = root.find("atom:entry", namespace)
    if entry is None:
        get_runtime_logger().warn("resolver.arxiv", "arXiv 未返回匹配论文", arxiv_id=arxiv_id)
        return _resolve_arxiv_metadata_fallback(target_paper, arxiv_id, reason="arxiv_no_entry")

    title = normalize_ws(entry.findtext("atom:title", default="", namespaces=namespace))
    entry_id = normalize_ws(entry.findtext("atom:id", default="", namespaces=namespace))
    resolved_arxiv = extract_arxiv_id(entry_id) or arxiv_id
    doi = None
    for candidate in entry.findall("arxiv:doi", arxiv_namespace):
        doi = normalize_ws(candidate.text or "")
        if doi:
            break

    resolved_arxiv = normalize_arxiv_id(resolved_arxiv) or arxiv_id
    source_ids = {"arxiv": resolved_arxiv}
    if doi:
        source_ids["doi"] = doi.lower()

    get_runtime_logger().detail(
        "resolver.arxiv",
        "arXiv 成功解析目标论文",
        arxiv_id=resolved_arxiv,
        has_doi=bool(doi),
    )
    return TargetPaper(
        canonical_id=resolved_arxiv,
        paper_query=target_paper.paper_query,
        paper_query_type=target_paper.paper_query_type,
        title=title or None,
        doi=doi.lower() if doi else None,
        source_ids=source_ids,
        resolve_status="resolved" if title else "unresolved",
    )


def resolve_by_title(target_paper: TargetPaper) -> TargetPaper:
    """Resolve a title clue by checking arXiv before Crossref exact matches."""
    title_query = normalize_ws(target_paper.paper_query or "")
    if not title_query:
        get_runtime_logger().warn("resolver.title", "标题查询为空")
        return mark_unresolved(target_paper, reason="empty title query")

    get_runtime_logger().detail("resolver.title", "正在通过标题解析目标论文", title=title_query)
    arxiv_match = search_arxiv_title_exact(title_query)
    crossref_match = search_crossref_title_exact(title_query)

    if arxiv_match:
        arxiv_id = normalize_arxiv_id(arxiv_match["arxiv_id"]) or arxiv_match["arxiv_id"]
        get_runtime_logger().detail("resolver.title", "标题精确匹配到 arXiv 记录", arxiv_id=arxiv_id)
        source_ids = {"arxiv": arxiv_id}
        if arxiv_match.get("doi"):
            source_ids["doi"] = arxiv_match["doi"].lower()
        return TargetPaper(
            canonical_id=arxiv_id,
            paper_query=target_paper.paper_query,
            paper_query_type=target_paper.paper_query_type,
            title=arxiv_match["title"],
            doi=arxiv_match.get("doi", "").lower() or None,
            source_ids=source_ids,
            resolve_status="resolved",
        )

    if crossref_match:
        get_runtime_logger().detail("resolver.title", "标题精确匹配到 Crossref 记录", doi=crossref_match.get("DOI"))
        return TargetPaper(
            canonical_id=(crossref_match.get("DOI") or title_query).lower(),
            paper_query=target_paper.paper_query,
            paper_query_type=target_paper.paper_query_type,
            title=first_title(crossref_match.get("title")) or title_query,
            doi=(crossref_match.get("DOI") or "").lower() or None,
            source_ids={"crossref": (crossref_match.get("DOI") or "").lower(), "doi": (crossref_match.get("DOI") or "").lower()},
            resolve_status="resolved",
        )

    get_runtime_logger().warn("resolver.title", "标题解析未找到精确匹配", title=title_query)
    return TargetPaper(
        canonical_id=None,
        paper_query=target_paper.paper_query,
        paper_query_type=target_paper.paper_query_type,
        title=title_query,
        doi=None,
        source_ids={},
        resolve_status="uncertain",
    )


def search_crossref_title_exact(title_query: str) -> Optional[dict[str, object]]:
    """Return the Crossref work whose normalized title exactly matches the query."""
    response = _get_with_retry(
        f"https://api.crossref.org/works?query.title={quote(title_query)}&rows=5",
        TITLE_RESOLVE_RETRY,
    )
    items = response.json()["message"].get("items", [])
    normalized_query = normalize_title(title_query)
    for item in items:
        title = first_title(item.get("title"))
        if title and normalize_title(title) == normalized_query:
            return item
    return None


def search_arxiv_title_exact(title_query: str) -> Optional[dict[str, str]]:
    """Return the arXiv entry whose normalized title exactly matches the query."""
    response = _get_with_retry(
        f"http://export.arxiv.org/api/query?search_query=ti:%22{quote(title_query)}%22&start=0&max_results=5",
        ARXIV_TITLE_RETRY,
    )
    root = ElementTree.fromstring(response.text)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    arxiv_namespace = {"arxiv": "http://arxiv.org/schemas/atom"}
    normalized_query = normalize_title(title_query)
    for entry in root.findall("atom:entry", namespace):
        title = normalize_ws(entry.findtext("atom:title", default="", namespaces=namespace))
        if normalize_title(title) != normalized_query:
            continue
        entry_id = normalize_ws(entry.findtext("atom:id", default="", namespaces=namespace))
        arxiv_id = extract_arxiv_id(entry_id)
        doi = None
        for candidate in entry.findall("arxiv:doi", arxiv_namespace):
            doi = normalize_ws(candidate.text or "")
            if doi:
                break
        if arxiv_id:
            return {"title": title, "arxiv_id": arxiv_id, "doi": doi or ""}
    return None


def _get_with_retry(url: str, policy: RetryPolicy) -> requests.Response:
    """Fetch resolver metadata through the shared network retry policy."""
    def fetch() -> requests.Response:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        return response

    return retry_call(fetch, policy)


def mark_unresolved(target_paper: TargetPaper, reason: str) -> TargetPaper:
    """Preserve the original target clue when metadata resolution cannot decide."""
    return TargetPaper(
        canonical_id=target_paper.canonical_id,
        paper_query=target_paper.paper_query,
        paper_query_type=target_paper.paper_query_type,
        title=target_paper.title,
        doi=target_paper.doi,
        source_ids=dict(target_paper.source_ids),
        resolve_status="unresolved" if target_paper.paper_query_type != "title" else "uncertain",
    )


def _resolved_arxiv_stub(target_paper: TargetPaper, arxiv_id: str) -> TargetPaper:
    return TargetPaper(
        canonical_id=arxiv_id,
        paper_query=target_paper.paper_query,
        paper_query_type=target_paper.paper_query_type,
        title=target_paper.title or f"arXiv:{arxiv_id}",
        doi=target_paper.doi,
        source_ids={"arxiv": arxiv_id, **({"doi": target_paper.doi.lower()} if target_paper.doi else {})},
        resolve_status="resolved",
    )


def _resolve_arxiv_metadata_fallback(target_paper: TargetPaper, arxiv_id: str, *, reason: str) -> TargetPaper:
    """Resolve arXiv metadata through structured APIs and optional web-search fallback."""
    semantic = _resolve_arxiv_from_semantic_scholar(target_paper, arxiv_id)
    if semantic is not None:
        return semantic
    web = _resolve_arxiv_from_web_search(target_paper, arxiv_id, reason=reason)
    if web is not None:
        return web
    return _resolved_arxiv_stub(target_paper, arxiv_id)


def _resolve_arxiv_from_semantic_scholar(target_paper: TargetPaper, arxiv_id: str) -> TargetPaper | None:
    """Use Semantic Scholar paper lookup as a stable title fallback for arXiv IDs."""
    try:
        paper_ref = SemanticScholarClient(max_retries=1, backoff_seconds=1.0).resolve_target_paper(
            TargetPaper(
                canonical_id=arxiv_id,
                paper_query=arxiv_id,
                paper_query_type="arxiv",
                source_ids={"arxiv": arxiv_id},
            )
        )
    except Exception as exc:
        get_runtime_logger().warn(
            "resolver.semantic_scholar",
            "Semantic Scholar 目标论文标题兜底失败",
            arxiv_id=arxiv_id,
            error_type=exc.__class__.__name__,
        )
        return None
    title = normalize_ws(str(paper_ref.get("title") or ""))
    if not _looks_like_real_title(title, arxiv_id):
        return None
    doi = normalize_ws(str(paper_ref.get("doi") or "")) or target_paper.doi
    source_ids = {
        "arxiv": arxiv_id,
        "semantic_scholar": str(paper_ref.get("paper_id") or paper_ref.get("source_record_id") or "").strip(),
    }
    if doi:
        source_ids["doi"] = doi.lower()
    get_runtime_logger().detail(
        "resolver.semantic_scholar",
        "Semantic Scholar 成功补全目标论文标题",
        arxiv_id=arxiv_id,
        title=title,
    )
    return TargetPaper(
        canonical_id=arxiv_id,
        paper_query=target_paper.paper_query,
        paper_query_type=target_paper.paper_query_type,
        title=title,
        doi=doi.lower() if doi else None,
        source_ids={key: value for key, value in source_ids.items() if value},
        resolve_status="resolved",
    )


def _resolve_arxiv_from_web_search(target_paper: TargetPaper, arxiv_id: str, *, reason: str) -> TargetPaper | None:
    """Use configured web-search API plus LLM verification to recover an arXiv title."""
    try:
        from apps.analyzer.config import build_llm, invoke_llm_with_retry, load_local_env

        load_local_env(override=True)
        search_client = GenericWebSearchClient.from_env()
        results = search_client.search(f"arXiv {arxiv_id} paper title", max_results=5)
    except WebSearchUnavailable as exc:
        get_runtime_logger().warn(
            "resolver.web_search",
            "通用搜索 API 未配置，跳过 Stage1 联网搜索兜底",
            arxiv_id=arxiv_id,
            reason=str(exc),
        )
        return None
    except Exception as exc:
        get_runtime_logger().warn(
            "resolver.web_search",
            "通用搜索 API 查询失败",
            arxiv_id=arxiv_id,
            error_type=exc.__class__.__name__,
        )
        return None

    if not results:
        get_runtime_logger().warn("resolver.web_search", "通用搜索 API 未返回结果", arxiv_id=arxiv_id)
        return None

    try:
        llm = build_llm()
        structured_llm = llm.with_structured_output(WebTitleResolutionModel, method="function_calling")
        decision = invoke_llm_with_retry(
            structured_llm,
            [
                {
                    "role": "system",
                    "content": (
                        "你正在从联网搜索结果中核验 arXiv 论文标题。"
                        "只允许根据给定搜索结果判断，不要凭记忆补全。"
                        "如果结果不能可靠对应指定 arXiv ID，title 必须返回 UNKNOWN。"
                        "confidence 必须是 high、medium、low 或 unknown。"
                        "evidence_zh 用中文简要说明依据。"
                    ),
                },
                {
                    "role": "user",
                    "content": _format_web_title_prompt(arxiv_id, results),
                },
            ],
            "阶段1联网搜索标题核验",
        )
    except Exception as exc:
        get_runtime_logger().warn(
            "resolver.web_search_llm",
            "LLM 无法核验联网搜索标题",
            arxiv_id=arxiv_id,
            error_type=exc.__class__.__name__,
        )
        return None

    title = normalize_ws(str(getattr(decision, "title", "") or ""))
    confidence = str(getattr(decision, "confidence", "") or "").strip().casefold()
    source_url = normalize_ws(str(getattr(decision, "source_url", "") or ""))
    if not _looks_like_real_title(title, arxiv_id) or confidence not in {"high", "medium"}:
        get_runtime_logger().warn(
            "resolver.web_search_llm",
            "LLM 未能从联网搜索结果确认目标论文标题",
            arxiv_id=arxiv_id,
            confidence=confidence or "unknown",
        )
        return None

    get_runtime_logger().detail(
        "resolver.web_search_llm",
        "联网搜索 + LLM 成功补全目标论文标题",
        arxiv_id=arxiv_id,
        title=title,
        confidence=confidence,
    )
    source_ids = {"arxiv": arxiv_id, "web_search": source_url, "web_search_reason": reason}
    return TargetPaper(
        canonical_id=arxiv_id,
        paper_query=target_paper.paper_query,
        paper_query_type=target_paper.paper_query_type,
        title=title,
        doi=target_paper.doi,
        source_ids={key: value for key, value in source_ids.items() if value},
        resolve_status="resolved",
    )


def _format_web_title_prompt(arxiv_id: str, results: list[WebSearchResult]) -> str:
    """Format search rows so the LLM can choose only evidence-backed titles."""
    lines = [f"Target arXiv ID: {arxiv_id}", "Search results:"]
    for index, result in enumerate(results, start=1):
        lines.append(
            "\n".join(
                [
                    f"{index}. title: {result.title}",
                    f"   url: {result.url}",
                    f"   snippet: {result.snippet}",
                    f"   source: {result.source}",
                ]
            )
        )
    return "\n".join(lines)


def _looks_like_real_title(title: str, arxiv_id: str) -> bool:
    """Reject placeholder IDs and empty values before accepting a resolved title."""
    normalized = normalize_ws(title)
    if not normalized:
        return False
    if normalized.strip().upper() == "UNKNOWN":
        return False
    if normalize_title(normalized) in {normalize_title(f"arXiv:{arxiv_id}"), normalize_title(arxiv_id)}:
        return False
    return bool(re.search(r"[A-Za-z]", normalized)) and len(normalized) >= 8


def first_title(value: object) -> Optional[str]:
    """Extract a normalized title string from Crossref-style title fields."""
    if isinstance(value, list) and value:
        return normalize_ws(str(value[0]))
    if isinstance(value, str) and value.strip():
        return normalize_ws(value)
    return None


def normalize_ws(text: str) -> str:
    """Collapse arbitrary whitespace in resolver metadata fields."""
    return " ".join(text.split())


def normalize_title(text: str) -> str:
    """Convert titles into comparable lowercase token strings."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def normalize_arxiv_id(value: str) -> Optional[str]:
    """Extract a versionless modern arXiv identifier from user or API text."""
    match = re.search(r"(?P<identifier>\d{4}\.\d{4,5})(?:v\d+)?", value, re.IGNORECASE)
    if not match:
        return None
    return match.group("identifier")


def extract_arxiv_id(value: str) -> Optional[str]:
    """Extract an arXiv identifier from canonical arXiv or DOI-style URLs."""
    match = re.search(r"(?:arxiv\.org/abs/|10\.48550/arxiv\.)(?P<identifier>\d{4}\.\d{4,5}(?:v\d+)?)", value, re.IGNORECASE)
    if match:
        return match.group("identifier")
    return None
