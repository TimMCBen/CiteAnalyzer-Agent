"""Validate Stage 5 PDF selection, fetching, and arXiv cache use."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.citation_sources.models import CitingPaper
from packages.paper_identity.models import CandidateWork
from packages.sentiment.fulltext import PDF_ARTIFACT_TEXT, fetch_fulltext_document, select_text_source
from packages.sentiment.fulltext import reset_arxiv_metadata_client_for_testing, search_arxiv_candidates_by_title
from packages.sentiment.fulltext import set_arxiv_metadata_client_for_testing
from packages.shared.models import TargetPaper
from scripts.test_agent.stage_logging import StageLogger

DEFAULT_SAMPLE_PATH = REPO_ROOT / "docs" / "generated" / "stage2-live-10.1145.3368089.3409740.json"


def load_stage2_sample(sample_path: Path) -> tuple[TargetPaper, list[CitingPaper]]:
    """Load saved Stage 2 target and citing-paper fixtures."""
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    fetch_result = payload["fetch_result"]
    target_paper = TargetPaper(
        canonical_id=None,
        paper_query=payload["target_doi"],
        paper_query_type="doi",
        title="Towards automated verification of smart contract fairness",
        doi=payload["target_doi"],
        source_ids={"doi": payload["target_doi"]},
        resolve_status="resolved",
    )
    citing_papers = [
        CitingPaper(
            canonical_id=item["canonical_id"],
            title=item["title"],
            doi=item.get("doi"),
            year=item.get("year"),
            authors=list(item.get("authors") or []),
            venue=item.get("venue"),
            abstract=item.get("abstract"),
            source_links=dict(item.get("source_links") or {}),
            source_names=list(item.get("source_names") or []),
            source_specific_ids=dict(item.get("source_specific_ids") or {}),
        )
        for item in fetch_result["citing_papers"]
    ]
    return target_paper, citing_papers


def build_local_source_links(citing_papers: list[CitingPaper], target_doi: str) -> Path:
    """Create local PDF fixtures for full-text tests."""
    temp_dir = Path(tempfile.mkdtemp(prefix="stage5-fixtures-", dir=REPO_ROOT))
    html_path = temp_dir / "citing-2.html"
    pdf_path = temp_dir / "citing-1.pdf"
    pdf2_path = temp_dir / "citing-2.pdf"
    pdf3_path = temp_dir / "citing-3.pdf"

    html_path.write_text(
        (
            "<html><body><article>"
            f"<p>Background reference to {target_doi}.</p>"
            "<p>This page exists to test HTML extraction only.</p>"
            "</article></body></html>"
        ),
        encoding="utf-8",
    )
    pdf_path.write_bytes(build_simple_pdf_bytes(f"Introduction. This PDF mentions {target_doi} to validate local PDF extraction."))
    pdf2_path.write_bytes(build_simple_pdf_bytes(f"Background. This PDF mentions {target_doi} to validate the second local PDF extraction."))
    pdf3_path.write_bytes(build_simple_pdf_bytes(f"Method. This second PDF mentions {target_doi} and should be preferred over the unsupported paired HTML source."))

    for paper in citing_papers:
        if paper.canonical_id == "citing-1":
            paper.source_links = {"local_pdf": str(pdf_path)}
            paper.abstract = None
        elif paper.canonical_id == "citing-2":
            paper.source_links = {"local_pdf": str(pdf2_path)}
            paper.abstract = None
        elif paper.canonical_id == "citing-3":
            paper.source_links = {"local_html": str(html_path), "local_pdf": str(pdf3_path)}
            paper.abstract = None
        elif paper.canonical_id == "citing-4":
            paper.source_links = {}
            paper.abstract = None
    return temp_dir


def build_simple_pdf_bytes(text: str) -> bytes:
    """Build a minimal PDF fixture containing the provided text."""
    safe_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content_lines = ["BT", "/F1 12 Tf", "72 720 Td"]
    for raw_line in wrap_text(text=safe_text, width=85):
        content_lines.append(f"({raw_line}) Tj")
        content_lines.append("0 -16 Td")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="ignore")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend((f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF").encode("ascii"))
    return bytes(pdf)


def wrap_text(text: str, width: int) -> list[str]:
    """Wrap fixture PDF text into simple content-stream lines."""
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    current_length = 0
    for word in words:
        projected = current_length + len(word) + (1 if current else 0)
        if projected > width and current:
            lines.append(" ".join(current))
            current = [word]
            current_length = len(word)
        else:
            current.append(word)
            current_length = projected
    if current:
        lines.append(" ".join(current))
    return lines


def assert_stage5_local_fulltext_validation(sample_path: Path = DEFAULT_SAMPLE_PATH) -> dict[str, object]:
    target_paper, citing_papers = load_stage2_sample(sample_path)
    temp_dir = build_local_source_links(citing_papers, target_paper.doi or "")
    save_dir = temp_dir / "saved"
    try:
        docs = {}
        for paper in citing_papers[:4]:
            docs[paper.canonical_id] = fetch_fulltext_document(
                paper,
                search_arxiv_fallback=False,
                save_dir=save_dir,
            )

        assert docs["citing-1"] is not None and docs["citing-1"].source_type == "pdf"
        assert docs["citing-2"] is not None and docs["citing-2"].source_type == "pdf"
        assert docs["citing-3"] is not None and docs["citing-3"].source_type == "pdf"
        assert docs["citing-4"] is None
        assert docs["citing-1"].text == PDF_ARTIFACT_TEXT
        assert docs["citing-2"].text == PDF_ARTIFACT_TEXT
        assert docs["citing-3"].text == PDF_ARTIFACT_TEXT
        assert docs["citing-1"].local_path and Path(docs["citing-1"].local_path).exists()
        assert docs["citing-2"].local_path and Path(docs["citing-2"].local_path).exists()
        assert docs["citing-3"].local_path and Path(docs["citing-3"].local_path).exists()
        assert docs["citing-1"].raw_path and Path(docs["citing-1"].raw_path).exists()
        assert docs["citing-2"].raw_path and Path(docs["citing-2"].raw_path).exists()
        assert docs["citing-3"].raw_path and Path(docs["citing-3"].raw_path).exists()
        return {
            "sample_path": str(sample_path),
            "temp_dir": str(temp_dir),
            "source_types": {paper_id: doc.source_type if doc else "missing" for paper_id, doc in docs.items()},
            "persisted": {
                paper_id: bool(doc and doc.local_path and Path(doc.local_path).exists()) for paper_id, doc in docs.items()
            },
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def assert_stage5_unavailable_paper_guidance(sample_path: Path = DEFAULT_SAMPLE_PATH) -> str:
    target_paper, citing_papers = load_stage2_sample(sample_path)
    _ = target_paper
    unavailable = next(paper for paper in citing_papers if paper.canonical_id == "citing-4")
    unavailable.doi = target_paper.doi
    unavailable.source_links = {"missing_local_pdf": str(REPO_ROOT / "downloaded-papers" / "missing-citing-4.pdf")}
    unavailable.abstract = "Short abstract fallback for unavailable fulltext."

    selection = select_text_source(
        unavailable,
        provided_documents=None,
        allow_network=True,
        search_arxiv_fallback=False,
    )

    assert selection.source_type == "unknown", selection
    assert selection.text is None, selection
    assert "no_text_available" in selection.evidence_note, selection.evidence_note
    assert "recovery=" in selection.evidence_note, selection.evidence_note
    assert "attach_local_pdf_via_source_links" in selection.evidence_note, selection.evidence_note
    assert "check_doi_landing_page" in selection.evidence_note, selection.evidence_note
    return selection.evidence_note


class FakeArxivMetadataClient:
    """Fake arXiv metadata client that tracks cache behavior."""
    def __init__(self) -> None:
        self.calls = 0
        self.cache_hits = 0
        self.request_count = 0
        self._cache: dict[str, list[CandidateWork]] = {}

    def search_by_title(self, title: str, *, max_results: int = 3) -> list[CandidateWork]:
        """Return cached or generated arXiv candidates for a title."""
        normalized = title.lower().strip()
        if normalized in self._cache:
            self.cache_hits += 1
            return list(self._cache[normalized])
        self.calls += 1
        self.request_count += 1
        self._cache[normalized] = [
            CandidateWork(
                source="arxiv",
                work_id="https://arxiv.org/abs/2504.19162",
                title=title,
                arxiv_id="2504.19162",
            )
        ]
        return list(self._cache[normalized])


def assert_stage5_arxiv_search_uses_shared_cache() -> dict[str, int]:
    fake_client = FakeArxivMetadataClient()
    set_arxiv_metadata_client_for_testing(fake_client)
    try:
        title = "SPC: Evolving Self-Play Critic via Adversarial Games for LLM Reasoning"
        first = search_arxiv_candidates_by_title(title)
        second = search_arxiv_candidates_by_title(title)

        assert first == second, (first, second)
        assert len(first) == 1, first
        assert fake_client.calls == 1, fake_client.calls
        assert fake_client.cache_hits == 1, fake_client.cache_hits
        return {"calls": fake_client.calls, "cache_hits": fake_client.cache_hits, "urls": len(first)}
    finally:
        reset_arxiv_metadata_client_for_testing()


def maybe_run_live_fetch_smoke(logger: StageLogger) -> None:
    """Run the optional live full-text fetch smoke test when enabled."""
    live_mode = str(os.getenv("STAGE5_FETCH_LIVE", "")).strip().lower()
    if live_mode not in {"1", "true", "yes"}:
        logger.detail("live_fetch_enabled=False env=STAGE5_FETCH_LIVE")
        return

    paper = CitingPaper(
        canonical_id="arxiv-smoke",
        title="Attention Is All You Need",
        doi="10.48550/arXiv.1706.03762",
        source_links={"arxiv": "https://arxiv.org/e-print/1706.03762"},
    )
    document = fetch_fulltext_document(paper, search_arxiv_fallback=True)
    assert document is not None, "live arxiv fetch returned no document"
    assert document.source_type == "pdf", document
    assert document.text == PDF_ARTIFACT_TEXT, document.text
    assert document.local_path and Path(document.local_path).exists(), "live arxiv fetch did not persist local PDF marker"
    assert document.raw_path and Path(document.raw_path).exists(), "live arxiv fetch did not preserve raw source"
    logger.pass_case(
        "live_fetch_smoke",
        detail=f"source_type={document.source_type} local_path={document.local_path} raw_path={document.raw_path}",
    )


def main() -> None:
    """Run Stage 5 PDF and cache contract assertions."""
    logger = StageLogger("stage5")
    logger.start()
    fulltext_detail = assert_stage5_local_fulltext_validation()
    logger.pass_case(
        "local_fulltext_validation",
        detail=(
            f"sample_path={fulltext_detail['sample_path']} temp_dir={fulltext_detail['temp_dir']} "
            f"source_types={fulltext_detail['source_types']} persisted={fulltext_detail['persisted']}"
        ),
    )
    evidence_note = assert_stage5_unavailable_paper_guidance()
    logger.pass_case("unavailable_paper_guidance", detail=f"evidence_note={evidence_note}")
    arxiv_cache = assert_stage5_arxiv_search_uses_shared_cache()
    logger.pass_case("arxiv_search_shared_cache", detail=str(arxiv_cache))
    maybe_run_live_fetch_smoke(logger)
    logger.done("stage5 validation passed")


if __name__ == "__main__":
    main()
