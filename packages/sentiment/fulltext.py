from __future__ import annotations

import io
import re
import tarfile
from pathlib import Path
from typing import Iterable, Mapping, Optional
from urllib.parse import quote, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from packages.citation_sources.models import CitingPaper
from packages.sentiment.models import FullTextDocument, TextSourceSelection

REQUEST_TIMEOUT_SECONDS = 20
TEXT_MIN_LENGTH = 80


def select_text_source(
    citing_paper: CitingPaper,
    provided_documents: Optional[Mapping[str, FullTextDocument]] = None,
    allow_network: bool = True,
    search_arxiv_fallback: bool = True,
) -> TextSourceSelection:
    document = (provided_documents or {}).get(citing_paper.canonical_id)
    if document and document.text.strip():
        return TextSourceSelection(
            citing_paper_id=citing_paper.canonical_id,
            text=document.text,
            source_type=document.source_type,
            source_label=document.source_label,
            evidence_note="text_loaded",
        )

    if allow_network:
        fetched_document = fetch_fulltext_document(citing_paper, search_arxiv_fallback=search_arxiv_fallback)
        if fetched_document and fetched_document.text.strip():
            return TextSourceSelection(
                citing_paper_id=citing_paper.canonical_id,
                text=fetched_document.text,
                source_type=fetched_document.source_type,
                source_label=fetched_document.source_label,
                evidence_note="text_fetched",
            )

    if citing_paper.abstract and citing_paper.abstract.strip():
        return TextSourceSelection(
            citing_paper_id=citing_paper.canonical_id,
            text=citing_paper.abstract,
            source_type="abstract",
            source_label="citing_paper.abstract",
            evidence_note="fallback_to_abstract_only",
        )

    return TextSourceSelection(
        citing_paper_id=citing_paper.canonical_id,
        text=None,
        source_type="unknown",
        source_label=None,
        evidence_note="no_text_available",
    )


def fetch_fulltext_document(citing_paper: CitingPaper, search_arxiv_fallback: bool = True) -> Optional[FullTextDocument]:
    for source_label, candidate in iter_fulltext_candidates(citing_paper, search_arxiv_fallback=search_arxiv_fallback):
        try:
            document = load_candidate_text(citing_paper.canonical_id, source_label, candidate)
        except Exception:
            continue
        if document and len(document.text.strip()) >= TEXT_MIN_LENGTH:
            return document
    return None


def iter_fulltext_candidates(citing_paper: CitingPaper, search_arxiv_fallback: bool = True) -> Iterable[tuple[str, str]]:
    scored: list[tuple[int, str, str]] = []
    seen: set[str] = set()

    for label, url in citing_paper.source_links.items():
        if not url or url in seen:
            continue
        seen.add(url)
        scored.append((score_candidate(url), label, url))

    if citing_paper.doi:
        doi_url = f"https://doi.org/{citing_paper.doi}"
        if doi_url not in seen:
            seen.add(doi_url)
            scored.append((score_candidate(doi_url), "doi", doi_url))

    if search_arxiv_fallback:
        for arxiv_url in search_arxiv_candidates_by_title(citing_paper.title):
            if arxiv_url not in seen:
                seen.add(arxiv_url)
                scored.append((score_candidate(arxiv_url), "arxiv_search", arxiv_url))

    for _, label, url in sorted(scored, key=lambda item: item[0]):
        yield label, url


def score_candidate(candidate: str) -> int:
    lowered = candidate.lower()
    if lowered.startswith("file://") or re.match(r"^[a-zA-Z]:[\\/]", candidate):
        return 0
    if lowered.endswith(".pdf"):
        return 1
    if "arxiv.org/e-print/" in lowered:
        return 2
    if "arxiv.org/src/" in lowered:
        return 2
    if "arxiv.org/html/" in lowered:
        return 3
    if "arxiv.org/abs/" in lowered:
        return 4
    if "doi.org/" in lowered:
        return 5
    if lowered.endswith(".tex") or lowered.endswith(".md") or lowered.endswith(".html"):
        return 6
    if "semanticscholar.org" in lowered:
        return 50
    return 10


def load_candidate_text(citing_paper_id: str, source_label: str, candidate: str) -> Optional[FullTextDocument]:
    parsed = urlparse(candidate)
    if looks_like_local_path(candidate, parsed):
        path = Path(parsed.path if parsed.scheme == "file" else candidate)
        if not path.exists() or path.is_dir():
            return None
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return FullTextDocument(
                citing_paper_id=citing_paper_id,
                text=extract_pdf_text(path.read_bytes()),
                source_type="pdf",
                source_label=str(path),
            )
        if suffix in {".html", ".htm"}:
            return FullTextDocument(
                citing_paper_id=citing_paper_id,
                text=extract_html_text(path.read_text(encoding="utf-8")),
                source_type="html",
                source_label=str(path),
            )
        if suffix in {".tex", ".latex"}:
            return FullTextDocument(
                citing_paper_id=citing_paper_id,
                text=extract_latex_text(path.read_text(encoding="utf-8")),
                source_type="latex",
                source_label=str(path),
            )
        if suffix in {".md", ".markdown"}:
            return FullTextDocument(
                citing_paper_id=citing_paper_id,
                text=normalize_whitespace(path.read_text(encoding="utf-8")),
                source_type="markdown",
                source_label=str(path),
            )
        return FullTextDocument(
            citing_paper_id=citing_paper_id,
            text=normalize_whitespace(path.read_text(encoding="utf-8")),
            source_type="fulltext",
            source_label=str(path),
        )

    response = requests.get(candidate, timeout=REQUEST_TIMEOUT_SECONDS, headers={"User-Agent": "CiteAnalyzer-Agent/0.1"})
    response.raise_for_status()

    content_type = (response.headers.get("content-type") or "").lower()
    lowered = candidate.lower()
    if lowered.endswith(".pdf") or "application/pdf" in content_type:
        return FullTextDocument(
            citing_paper_id=citing_paper_id,
            text=extract_pdf_text(response.content),
            source_type="pdf",
            source_label=candidate,
        )
    if "arxiv.org/e-print/" in lowered or "application/x-eprint-tar" in content_type:
        return FullTextDocument(
            citing_paper_id=citing_paper_id,
            text=extract_arxiv_source_text(response.content),
            source_type="latex",
            source_label=candidate,
        )
    if lowered.endswith(".tex"):
        return FullTextDocument(
            citing_paper_id=citing_paper_id,
            text=extract_latex_text(response.text),
            source_type="latex",
            source_label=candidate,
        )
    if lowered.endswith(".md") or lowered.endswith(".markdown") or "text/markdown" in content_type:
        return FullTextDocument(
            citing_paper_id=citing_paper_id,
            text=normalize_whitespace(response.text),
            source_type="markdown",
            source_label=candidate,
        )
    if "text/html" in content_type or lowered.endswith(".html") or lowered.endswith(".htm") or "arxiv.org/abs/" in lowered or "arxiv.org/html/" in lowered:
        return FullTextDocument(
            citing_paper_id=citing_paper_id,
            text=extract_html_text(response.text),
            source_type="html",
            source_label=candidate,
        )
    return FullTextDocument(
        citing_paper_id=citing_paper_id,
        text=normalize_whitespace(response.text),
        source_type="fulltext",
        source_label=candidate,
    )


def looks_like_local_path(candidate: str, parsed) -> bool:
    if parsed.scheme == "file":
        return True
    if parsed.scheme == "":
        return True
    return bool(re.match(r"^[a-zA-Z]:[\\/]", candidate))


def extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    chunks = [page.extract_text() or "" for page in reader.pages]
    return normalize_whitespace("\n".join(chunks))


def extract_html_text(content: str) -> str:
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return normalize_whitespace(soup.get_text(separator=" "))


def extract_latex_text(content: str) -> str:
    text = re.sub(r"(?<!\\)%.*", " ", content)
    text = re.sub(r"\\begin\{.*?\}|\\end\{.*?\}", " ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{([^{}]*)\})?", r" \1 ", text)
    text = re.sub(r"[{}]", " ", text)
    return normalize_whitespace(text)


def extract_arxiv_source_text(content: bytes) -> str:
    try:
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as archive:
            parts: list[str] = []
            for member in sorted(archive.getmembers(), key=lambda item: item.name):
                if not member.isfile() or not member.name.lower().endswith(".tex"):
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                parts.append(extract_latex_text(extracted.read().decode("utf-8", errors="ignore")))
            return normalize_whitespace("\n".join(parts))
    except tarfile.ReadError:
        return extract_latex_text(content.decode("utf-8", errors="ignore"))


def search_arxiv_candidates_by_title(title: str) -> list[str]:
    if not title.strip():
        return []

    query = quote(title.strip())
    url = f"http://export.arxiv.org/api/query?search_query=ti:%22{query}%22&start=0&max_results=3"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS, headers={"User-Agent": "CiteAnalyzer-Agent/0.1"})
        response.raise_for_status()
    except Exception:
        return []

    try:
        root = ElementTree.fromstring(response.text)
    except ElementTree.ParseError:
        return []

    normalized_title = normalize_for_title(title)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    urls: list[str] = []
    for entry in root.findall("atom:entry", namespace):
        entry_title = entry.findtext("atom:title", default="", namespaces=namespace)
        if not titles_look_related(normalized_title, normalize_for_title(entry_title)):
            continue
        entry_id = entry.findtext("atom:id", default="", namespaces=namespace).strip()
        arxiv_id = extract_arxiv_id(entry_id)
        if not arxiv_id:
            continue
        urls.extend(
            [
                f"https://arxiv.org/e-print/{arxiv_id}",
                f"https://arxiv.org/html/{arxiv_id}",
                f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            ]
        )
    return urls


def titles_look_related(left: str, right: str) -> bool:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens)
    return overlap >= max(3, min(len(left_tokens), len(right_tokens)) // 2)


def extract_arxiv_id(value: str) -> Optional[str]:
    if not value:
        return None
    match = re.search(r"(?:arxiv\.org/(?:abs|pdf|html|e-print)/|10\.48550/arxiv\.)(?P<identifier>\d{4}\.\d{4,5}(?:v\d+)?)", value, re.IGNORECASE)
    if match:
        return match.group("identifier")
    return None


def normalize_for_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())
