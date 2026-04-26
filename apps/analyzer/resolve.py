from __future__ import annotations

import re
from typing import Optional
from urllib.parse import quote
from xml.etree import ElementTree

import requests

from packages.shared.models import TargetPaper

REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "CiteAnalyzer-Agent/0.1"


def resolve_target_paper_metadata(target_paper: TargetPaper) -> TargetPaper:
    query_type = target_paper.paper_query_type
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
    response = requests.get(
        f"https://api.crossref.org/works/{doi}",
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    message = response.json()["message"]
    title = first_title(message.get("title"))
    if not title:
        return mark_unresolved(target_paper, reason="crossref returned no title for doi")

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
        return mark_unresolved(target_paper, reason="invalid arxiv identifier")

    response = requests.get(
        f"http://export.arxiv.org/api/query?id_list={quote(arxiv_id)}",
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    root = ElementTree.fromstring(response.text)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    arxiv_namespace = {"arxiv": "http://arxiv.org/schemas/atom"}
    entry = root.find("atom:entry", namespace)
    if entry is None:
        return mark_unresolved(target_paper, reason="arxiv returned no matching entry")

    title = normalize_ws(entry.findtext("atom:title", default="", namespaces=namespace))
    entry_id = normalize_ws(entry.findtext("atom:id", default="", namespaces=namespace))
    resolved_arxiv = extract_arxiv_id(entry_id) or arxiv_id
    doi = None
    for candidate in entry.findall("arxiv:doi", arxiv_namespace):
        doi = normalize_ws(candidate.text or "")
        if doi:
            break

    source_ids = {"arxiv": resolved_arxiv}
    if doi:
        source_ids["doi"] = doi.lower()

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
        return mark_unresolved(target_paper, reason="empty title query")

    arxiv_match = search_arxiv_title_exact(title_query)
    crossref_match = search_crossref_title_exact(title_query)

    if arxiv_match:
        source_ids = {"arxiv": arxiv_match["arxiv_id"]}
        if arxiv_match.get("doi"):
            source_ids["doi"] = arxiv_match["doi"].lower()
        return TargetPaper(
            canonical_id=arxiv_match["arxiv_id"],
            paper_query=target_paper.paper_query,
            paper_query_type=target_paper.paper_query_type,
            title=arxiv_match["title"],
            doi=arxiv_match.get("doi", "").lower() or None,
            source_ids=source_ids,
            resolve_status="resolved",
        )

    if crossref_match:
        return TargetPaper(
            canonical_id=(crossref_match.get("DOI") or title_query).lower(),
            paper_query=target_paper.paper_query,
            paper_query_type=target_paper.paper_query_type,
            title=first_title(crossref_match.get("title")) or title_query,
            doi=(crossref_match.get("DOI") or "").lower() or None,
            source_ids={"crossref": (crossref_match.get("DOI") or "").lower(), "doi": (crossref_match.get("DOI") or "").lower()},
            resolve_status="resolved",
        )

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
    response = requests.get(
        f"https://api.crossref.org/works?query.title={quote(title_query)}&rows=5",
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    items = response.json()["message"].get("items", [])
    normalized_query = normalize_title(title_query)
    for item in items:
        title = first_title(item.get("title"))
        if title and normalize_title(title) == normalized_query:
            return item
    return None


def search_arxiv_title_exact(title_query: str) -> Optional[dict[str, str]]:
    response = requests.get(
        f"http://export.arxiv.org/api/query?search_query=ti:%22{quote(title_query)}%22&start=0&max_results=5",
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
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
