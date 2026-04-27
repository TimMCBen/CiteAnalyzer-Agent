from __future__ import annotations

import io
import shutil
import re
from dataclasses import dataclass, field
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
DEFAULT_STAGE5_DOWNLOAD_DIR = Path("downloaded-papers") / "stage5"


@dataclass
class LoadedDocumentPayload:
    document: Optional[FullTextDocument]
    raw_bytes: Optional[bytes] = None
    raw_suffix: Optional[str] = None
    extracted_files: dict[str, str] = field(default_factory=dict)
    source_file_path: Optional[Path] = None


def select_text_source(
    citing_paper: CitingPaper,
    provided_documents: Optional[Mapping[str, FullTextDocument]] = None,
    allow_network: bool = True,
    search_arxiv_fallback: bool = True,
    save_dir: Optional[Path] = None,
) -> TextSourceSelection:
    document = (provided_documents or {}).get(citing_paper.canonical_id)
    if document and (document.text.strip() or document.raw_path):
        return TextSourceSelection(
            citing_paper_id=citing_paper.canonical_id,
            text=document.text,
            source_type=document.source_type,
            source_label=document.source_label,
            local_path=document.local_path,
            raw_path=document.raw_path,
            extracted_dir=document.extracted_dir,
            evidence_note="text_loaded",
        )

    if allow_network:
        fetched_document = fetch_fulltext_document(
            citing_paper,
            search_arxiv_fallback=search_arxiv_fallback,
            save_dir=save_dir,
        )
        if fetched_document and fetched_document.text.strip():
            return TextSourceSelection(
                citing_paper_id=citing_paper.canonical_id,
                text=fetched_document.text,
                source_type=fetched_document.source_type,
                source_label=fetched_document.source_label,
                local_path=fetched_document.local_path,
                raw_path=fetched_document.raw_path,
                extracted_dir=fetched_document.extracted_dir,
                evidence_note="text_fetched",
            )

    if citing_paper.abstract and citing_paper.abstract.strip():
        return TextSourceSelection(
            citing_paper_id=citing_paper.canonical_id,
            text=citing_paper.abstract,
            source_type="abstract",
            source_label="citing_paper.abstract",
            local_path=None,
            raw_path=None,
            extracted_dir=None,
            evidence_note="fallback_to_abstract_only",
        )

    return TextSourceSelection(
        citing_paper_id=citing_paper.canonical_id,
        text=None,
        source_type="unknown",
        source_label=None,
        local_path=None,
        raw_path=None,
        extracted_dir=None,
        evidence_note="no_text_available",
    )


def fetch_fulltext_document(
    citing_paper: CitingPaper,
    search_arxiv_fallback: bool = True,
    save_dir: Optional[Path] = None,
) -> Optional[FullTextDocument]:
    for source_label, candidate in iter_fulltext_candidates(citing_paper, search_arxiv_fallback=search_arxiv_fallback):
        try:
            payload = load_candidate_text(citing_paper.canonical_id, source_label, candidate)
        except Exception:
            continue
        document = payload.document
        if document and len(document.text.strip()) >= TEXT_MIN_LENGTH:
            persist_fulltext_document(
                citing_paper=citing_paper,
                document=document,
                payload=payload,
                save_dir=save_dir,
            )
            return document
    return None


def iter_fulltext_candidates(citing_paper: CitingPaper, search_arxiv_fallback: bool = True) -> Iterable[tuple[str, str]]:
    scored: list[tuple[int, str, str]] = []
    seen: set[str] = set()

    for label, url in citing_paper.source_links.items():
        if not url:
            continue
        for candidate in expand_candidate_variants(url):
            if candidate in seen:
                continue
            seen.add(candidate)
            scored.append((score_candidate(candidate), label, candidate))

    if search_arxiv_fallback:
        for arxiv_url in search_arxiv_candidates_by_title(citing_paper.title):
            if arxiv_url in seen:
                continue
            seen.add(arxiv_url)
            scored.append((score_candidate(arxiv_url), "arxiv_search", arxiv_url))

    for _, label, url in sorted(scored, key=lambda item: item[0]):
        yield label, url


def expand_candidate_variants(candidate: str) -> list[str]:
    lowered = candidate.lower()
    arxiv_id = extract_arxiv_id(candidate)
    if arxiv_id and ("arxiv.org/e-print/" in lowered or "arxiv.org/src/" in lowered):
        return [
            f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            f"https://arxiv.org/html/{arxiv_id}",
            f"https://arxiv.org/abs/{arxiv_id}",
        ]
    return [candidate]


def score_candidate(candidate: str) -> int:
    lowered = candidate.lower()
    if lowered.startswith("file://") or re.match(r"^[a-zA-Z]:[\\/]", candidate):
        if lowered.endswith(".pdf"):
            return 0
        if lowered.endswith((".html", ".htm")):
            return 1
        if lowered.endswith((".tex", ".latex", ".md", ".markdown")):
            return 5
        return 10
    if lowered.endswith(".pdf"):
        return 1
    if "arxiv.org/html/" in lowered:
        return 2
    if "arxiv.org/abs/" in lowered:
        return 3
    if lowered.endswith(".tex") or lowered.endswith(".md") or lowered.endswith(".html"):
        return 10
    if "semanticscholar.org" in lowered:
        return 50
    return 20


def load_candidate_text(citing_paper_id: str, source_label: str, candidate: str) -> LoadedDocumentPayload:
    parsed = urlparse(candidate)
    if looks_like_local_path(candidate, parsed):
        path = Path(parsed.path if parsed.scheme == "file" else candidate)
        if not path.exists() or path.is_dir():
            return LoadedDocumentPayload(document=None)
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return LoadedDocumentPayload(
                document=FullTextDocument(
                    citing_paper_id=citing_paper_id,
                    text=extract_pdf_text(path.read_bytes()),
                    source_type="pdf",
                    source_label=str(path),
                ),
                source_file_path=path,
            )
        if suffix in {".html", ".htm"}:
            return LoadedDocumentPayload(
                document=FullTextDocument(
                    citing_paper_id=citing_paper_id,
                    text=extract_html_text(path.read_text(encoding="utf-8")),
                    source_type="html",
                    source_label=str(path),
                ),
                source_file_path=path,
            )
        if suffix in {".tex", ".latex"}:
            return LoadedDocumentPayload(
                document=FullTextDocument(
                    citing_paper_id=citing_paper_id,
                    text=extract_latex_text(path.read_text(encoding="utf-8")),
                    source_type="latex",
                    source_label=str(path),
                ),
                source_file_path=path,
            )
        if suffix in {".md", ".markdown"}:
            return LoadedDocumentPayload(
                document=FullTextDocument(
                    citing_paper_id=citing_paper_id,
                    text=normalize_whitespace(path.read_text(encoding="utf-8")),
                    source_type="markdown",
                    source_label=str(path),
                ),
                source_file_path=path,
            )
        return LoadedDocumentPayload(
            document=FullTextDocument(
                citing_paper_id=citing_paper_id,
                text=normalize_whitespace(path.read_text(encoding="utf-8")),
                source_type="fulltext",
                source_label=str(path),
            ),
            source_file_path=path,
        )

    response = requests.get(candidate, timeout=REQUEST_TIMEOUT_SECONDS, headers={"User-Agent": "CiteAnalyzer-Agent/0.1"})
    response.raise_for_status()

    content_type = (response.headers.get("content-type") or "").lower()
    lowered = candidate.lower()
    if "arxiv.org/e-print/" in lowered or "arxiv.org/src/" in lowered:
        arxiv_id = extract_arxiv_id(candidate)
        if arxiv_id:
            return load_candidate_text(
                citing_paper_id=citing_paper_id,
                source_label=source_label,
                candidate=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            )
    if lowered.endswith(".pdf") or "application/pdf" in content_type:
        return LoadedDocumentPayload(
            document=FullTextDocument(
                citing_paper_id=citing_paper_id,
                text=extract_pdf_text(response.content),
                source_type="pdf",
                source_label=candidate,
            ),
            raw_bytes=response.content,
            raw_suffix=".pdf",
        )
    if lowered.endswith(".tex"):
        return LoadedDocumentPayload(
            document=FullTextDocument(
                citing_paper_id=citing_paper_id,
                text=extract_latex_text(response.text),
                source_type="latex",
                source_label=candidate,
            ),
            raw_bytes=response.content,
            raw_suffix=".tex",
        )
    if lowered.endswith(".md") or lowered.endswith(".markdown") or "text/markdown" in content_type:
        return LoadedDocumentPayload(
            document=FullTextDocument(
                citing_paper_id=citing_paper_id,
                text=normalize_whitespace(response.text),
                source_type="markdown",
                source_label=candidate,
            ),
            raw_bytes=response.content,
            raw_suffix=".md",
        )
    if "text/html" in content_type or lowered.endswith(".html") or lowered.endswith(".htm") or "arxiv.org/abs/" in lowered or "arxiv.org/html/" in lowered:
        return LoadedDocumentPayload(
            document=FullTextDocument(
                citing_paper_id=citing_paper_id,
                text=extract_html_text(response.text),
                source_type="html",
                source_label=candidate,
            ),
            raw_bytes=response.content,
            raw_suffix=".html",
        )
    return LoadedDocumentPayload(
        document=FullTextDocument(
            citing_paper_id=citing_paper_id,
            text=normalize_whitespace(response.text),
            source_type="fulltext",
            source_label=candidate,
        ),
        raw_bytes=response.content,
        raw_suffix=".txt",
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
                f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                f"https://arxiv.org/html/{arxiv_id}",
                f"https://arxiv.org/abs/{arxiv_id}",
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


def persist_fulltext_document(
    citing_paper: CitingPaper,
    document: FullTextDocument,
    payload: LoadedDocumentPayload,
    save_dir: Optional[Path] = None,
) -> None:
    base_dir = (save_dir or DEFAULT_STAGE5_DOWNLOAD_DIR).resolve()
    base_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(citing_paper.title)
    paper_dir = base_dir / f"{citing_paper.canonical_id}__{slug}"
    paper_dir.mkdir(parents=True, exist_ok=True)

    parsed_path = paper_dir / f"parsed__{document.source_type}.txt"
    parsed_path.write_text(document.text, encoding="utf-8")
    document.local_path = str(parsed_path)

    if payload.raw_bytes is not None and payload.raw_suffix:
        raw_path = paper_dir / f"source{payload.raw_suffix}"
        raw_path.write_bytes(payload.raw_bytes)
        document.raw_path = str(raw_path)
    elif payload.source_file_path is not None and payload.source_file_path.exists():
        raw_path = paper_dir / payload.source_file_path.name
        shutil.copy2(payload.source_file_path, raw_path)
        document.raw_path = str(raw_path)

    if payload.extracted_files:
        extracted_dir = paper_dir / "extracted"
        extracted_dir.mkdir(parents=True, exist_ok=True)
        for relative_name, content in payload.extracted_files.items():
            safe_name = Path(relative_name)
            out_path = extracted_dir / safe_name
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
        document.extracted_dir = str(extracted_dir)


def slugify(text: str, limit: int = 80) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip()).strip("_").lower()
    if not normalized:
        return "untitled"
    return normalized[:limit]
