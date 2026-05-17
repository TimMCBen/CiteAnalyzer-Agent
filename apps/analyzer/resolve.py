from __future__ import annotations

import re
from typing import Optional
from urllib.parse import quote
from xml.etree import ElementTree

import requests

from packages.shared.models import TargetPaper
from packages.shared.network_retry import RetryExhaustedError, RetryPolicy, retry_call
from packages.shared.runtime_logging import get_runtime_logger

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


def resolve_target_paper_metadata(target_paper: TargetPaper) -> TargetPaper:
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
                "arXiv 元数据接口限流，使用 arXiv ID 继续进入 Semantic Scholar 主链路",
                arxiv_id=arxiv_id,
            )
            return _resolved_arxiv_stub(target_paper, arxiv_id)
        get_runtime_logger().warn(
            "resolver.arxiv",
            "arXiv 元数据接口多次连接失败，使用 arXiv ID 继续进入 Semantic Scholar 主链路",
            arxiv_id=arxiv_id,
            error_type=exc.reason,
        )
        return _resolved_arxiv_stub(target_paper, arxiv_id)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 429:
            get_runtime_logger().warn(
                "resolver.arxiv",
                "arXiv 元数据接口限流，使用 arXiv ID 继续进入 Semantic Scholar 主链路",
                arxiv_id=arxiv_id,
            )
            return _resolved_arxiv_stub(target_paper, arxiv_id)
        raise
    except requests.RequestException as exc:
        get_runtime_logger().warn(
            "resolver.arxiv",
            "arXiv 元数据接口连接失败，使用 arXiv ID 继续进入 Semantic Scholar 主链路",
            arxiv_id=arxiv_id,
            error_type=exc.__class__.__name__,
        )
        return _resolved_arxiv_stub(target_paper, arxiv_id)
    root = ElementTree.fromstring(response.text)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    arxiv_namespace = {"arxiv": "http://arxiv.org/schemas/atom"}
    entry = root.find("atom:entry", namespace)
    if entry is None:
        get_runtime_logger().warn("resolver.arxiv", "arXiv 未返回匹配论文", arxiv_id=arxiv_id)
        return mark_unresolved(target_paper, reason="arxiv returned no matching entry")

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


def first_title(value: object) -> Optional[str]:
    if isinstance(value, list) and value:
        return normalize_ws(str(value[0]))
    if isinstance(value, str) and value.strip():
        return normalize_ws(value)
    return None


def normalize_ws(text: str) -> str:
    return " ".join(text.split())


def normalize_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def normalize_arxiv_id(value: str) -> Optional[str]:
    match = re.search(r"(?P<identifier>\d{4}\.\d{4,5})(?:v\d+)?", value, re.IGNORECASE)
    if not match:
        return None
    return match.group("identifier")


def extract_arxiv_id(value: str) -> Optional[str]:
    match = re.search(r"(?:arxiv\.org/abs/|10\.48550/arxiv\.)(?P<identifier>\d{4}\.\d{4,5}(?:v\d+)?)", value, re.IGNORECASE)
    if match:
        return match.group("identifier")
    return None
