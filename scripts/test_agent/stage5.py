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
from packages.sentiment import analyze_citation_sentiments, locate_reference_context_with_llm
from packages.sentiment.fulltext import fetch_fulltext_document
from packages.sentiment.models import ReferenceMatch
from packages.shared.models import TargetPaper

DEFAULT_SAMPLE_PATH = REPO_ROOT / "docs" / "generated" / "stage2-live-10.1145.3368089.3409740.json"


def load_stage2_sample(sample_path: Path) -> tuple[TargetPaper, list[CitingPaper]]:
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    fetch_result = payload["fetch_result"]

    target_paper = TargetPaper(
        canonical_id=None,
        paper_query=payload["target_doi"],
        paper_query_type="doi",
        title=None,
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
    temp_dir = Path(tempfile.mkdtemp(prefix="stage5-fixtures-", dir=REPO_ROOT))
    html_path = temp_dir / "citing-2.html"
    tex_path = temp_dir / "citing-3.tex"
    pdf_path = temp_dir / "citing-1.pdf"
    indirect_html_path = temp_dir / "citing-5.html"

    html_path.write_text(
        (
            "<html><body><article>"
            f"<p>We cite {target_doi} as background literature on smart-contract transparency and human-centric concerns.</p>"
            "<p>The paper is referenced here to frame the surrounding design space rather than to evaluate its claims.</p>"
            "</article></body></html>"
        ),
        encoding="utf-8",
    )
    tex_path.write_text(
        (
            "\\section{Background}\n"
            f"However, {target_doi} does not model fairness constraints and cannot explain fund-stealing scenarios in DeFi protocols. "
            "This limitation motivates our fairness validation design.\n"
        ),
        encoding="utf-8",
    )
    indirect_html_path.write_text(
        (
            "<html><body><article>"
            "<p>Earlier work gave the first systematic treatment of open-secret vulnerabilities in smart contracts.</p>"
            "<p>We rely on that conceptual framing when discussing attacker-visible information leakage.</p>"
            "</article></body></html>"
        ),
        encoding="utf-8",
    )
    pdf_path.write_bytes(
        build_simple_pdf_bytes(
            f"Our detector explicitly builds on the vulnerability model introduced in {target_doi}. "
            "Following that work, we extend the analysis pipeline to identify open-secret attack paths."
        )
    )

    for paper in citing_papers:
        if paper.canonical_id == "citing-1":
            paper.source_links = {"local_pdf": str(pdf_path)}
            paper.abstract = None
        elif paper.canonical_id == "citing-2":
            paper.source_links = {"local_html": str(html_path)}
            paper.abstract = None
        elif paper.canonical_id == "citing-3":
            paper.source_links = {"local_tex": str(tex_path)}
            paper.abstract = None
        elif paper.canonical_id == "citing-4":
            paper.source_links = {}
            paper.abstract = None
        elif paper.canonical_id == "citing-5":
            paper.source_links = {"local_html": str(indirect_html_path)}
            paper.abstract = None
    return temp_dir


def build_simple_pdf_bytes(text: str) -> bytes:
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
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF"
        ).encode("ascii")
    )
    return bytes(pdf)


def wrap_text(text: str, width: int) -> list[str]:
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


def fake_llm_reference_matcher(text: str, target_paper: TargetPaper) -> ReferenceMatch:
    marker = "first systematic treatment of open-secret vulnerabilities"
    start = text.lower().find(marker)
    if start < 0:
        return ReferenceMatch(
            matched_target_reference=None,
            context_text=None,
            mention_span=None,
            evidence_note="llm_no_match:fixture_marker_missing",
        )
    sentence_end = text.find(".", start)
    end = len(text) if sentence_end < 0 else sentence_end + 1
    return ReferenceMatch(
        matched_target_reference=f"llm:title:{target_paper.title or target_paper.paper_query or 'unknown'}",
        context_text=text[start:end].strip(),
        mention_span=(start, end),
        evidence_note="matched_by_llm:semantic_fixture_match",
    )


def assert_stage5_local_validation(sample_path: Path = DEFAULT_SAMPLE_PATH) -> None:
    target_paper, citing_papers = load_stage2_sample(sample_path)
    target_paper.title = "OSVHunter: Detecting Publicly Observable Information Abuse in Ethereum Programs"
    temp_dir = build_local_source_links(citing_papers, target_paper.doi or "")
    try:
        result = analyze_citation_sentiments(
            target_paper=target_paper,
            citing_papers=citing_papers,
            fulltext_documents=None,
            allow_network=True,
            search_arxiv_fallback=False,
            use_llm_reference_fallback=True,
            llm_reference_matcher=fake_llm_reference_matcher,
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    labels = {context.citing_paper_id: context.sentiment_label for context in result.contexts}
    evidence_notes = {context.citing_paper_id: context.evidence_note for context in result.contexts}
    source_types = {context.citing_paper_id: context.text_source_type for context in result.contexts}

    assert len(result.contexts) == 5, f"expected 5 citation contexts, got {len(result.contexts)}"
    assert labels["citing-1"] == "positive", labels
    assert labels["citing-2"] == "neutral", labels
    assert labels["citing-3"] == "critical", labels
    assert labels["citing-4"] == "unknown", labels
    assert labels["citing-5"] == "neutral", labels

    assert evidence_notes["citing-1"].startswith("matched_by_doi; rule_positive"), evidence_notes["citing-1"]
    assert evidence_notes["citing-2"].endswith("default_neutral_without_polarized_cues"), evidence_notes["citing-2"]
    assert "rule_critical" in evidence_notes["citing-3"], evidence_notes["citing-3"]
    assert evidence_notes["citing-4"] == "no_text_available", evidence_notes["citing-4"]
    assert evidence_notes["citing-5"].startswith("matched_by_llm:semantic_fixture_match"), evidence_notes["citing-5"]
    assert source_types["citing-1"] == "pdf", source_types
    assert source_types["citing-2"] == "html", source_types
    assert source_types["citing-3"] == "latex", source_types
    assert source_types["citing-4"] == "unknown", source_types
    assert source_types["citing-5"] == "html", source_types

    summary = result.summary
    assert summary.total_candidates == 5, summary
    assert summary.fulltext_available == 4, summary
    assert summary.context_found == 4, summary
    assert summary.classified_count == 4, summary
    assert summary.unknown_count == 1, summary
    assert summary.label_counts == {
        "positive": 1,
        "neutral": 2,
        "critical": 1,
        "unknown": 1,
    }, summary.label_counts


def maybe_run_live_llm_smoke() -> None:
    live_mode = str(os.getenv("STAGE5_LIVE", "")).strip().lower()
    if live_mode not in {"1", "true", "yes"}:
        return

    target_paper = TargetPaper(
        canonical_id=None,
        paper_query="10.1145/3368089.3409740",
        paper_query_type="doi",
        title="OSVHunter: Detecting Publicly Observable Information Abuse in Ethereum Programs",
        doi="10.1145/3368089.3409740",
        source_ids={"doi": "10.1145/3368089.3409740"},
        resolve_status="resolved",
    )
    text = (
        "Prior work offered the first systematic treatment of open-secret vulnerabilities in smart contracts and clarified "
        "how attacker-visible information can be abused without breaking contract logic. We adopt that framing as the basis "
        "for our discussion of information leakage."
    )
    match = locate_reference_context_with_llm(text=text, target_paper=target_paper)
    assert match.context_text, f"live llm failed to locate indirect reference: {match.evidence_note}"
    print("[PASS] stage5::live_llm_reference_smoke")


def maybe_run_live_fetch_smoke() -> None:
    live_mode = str(os.getenv("STAGE5_FETCH_LIVE", "")).strip().lower()
    if live_mode not in {"1", "true", "yes"}:
        return

    paper = CitingPaper(
        canonical_id="arxiv-smoke",
        title="Attention Is All You Need",
        doi="10.48550/arXiv.1706.03762",
        source_links={"arxiv": "https://arxiv.org/e-print/1706.03762"},
    )
    document = fetch_fulltext_document(paper, search_arxiv_fallback=True)
    assert document is not None, "live arxiv fetch returned no document"
    assert document.source_type in {"latex", "html", "pdf"}, document
    assert len(document.text) > 1000, f"live arxiv fetch returned too little text: {len(document.text)}"
    print("[PASS] stage5::live_fetch_smoke")


def main() -> None:
    assert_stage5_local_validation()
    print("[PASS] stage5::local_sentiment_validation")
    maybe_run_live_llm_smoke()
    maybe_run_live_fetch_smoke()
    print("stage5 validation passed")


if __name__ == "__main__":
    main()
