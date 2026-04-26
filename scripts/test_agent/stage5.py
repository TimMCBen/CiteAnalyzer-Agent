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
from packages.sentiment.fulltext import fetch_fulltext_document
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

    html_path.write_text(
        (
            "<html><body><article>"
            f"<p>Background reference to {target_doi}.</p>"
            "<p>This page exists to test HTML extraction only.</p>"
            "</article></body></html>"
        ),
        encoding="utf-8",
    )
    tex_path.write_text(
        (
            "\\section{Intro}\n"
            f"Prior work {target_doi} is mentioned here for latex extraction.\n"
            "\\section{References}\n"
            f"[7] Target Work. {target_doi}. A First Systematic Study of Open-Secret Vulnerabilities in Smart Contracts.\n"
        ),
        encoding="utf-8",
    )
    pdf_path.write_bytes(build_simple_pdf_bytes(f"Introduction. This PDF mentions {target_doi} to validate local PDF extraction."))

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
    pdf.extend((f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF").encode("ascii"))
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


def assert_stage5_local_fulltext_validation(sample_path: Path = DEFAULT_SAMPLE_PATH) -> None:
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
    finally:
        pass

    try:
        assert docs["citing-1"] is not None and docs["citing-1"].source_type == "pdf"
        assert docs["citing-2"] is not None and docs["citing-2"].source_type == "html"
        assert docs["citing-3"] is not None and docs["citing-3"].source_type == "latex"
        assert docs["citing-4"] is None
        assert target_paper.doi in docs["citing-1"].text
        assert target_paper.doi in docs["citing-2"].text
        assert target_paper.doi in docs["citing-3"].text
        assert docs["citing-1"].local_path and Path(docs["citing-1"].local_path).exists()
        assert docs["citing-2"].local_path and Path(docs["citing-2"].local_path).exists()
        assert docs["citing-3"].local_path and Path(docs["citing-3"].local_path).exists()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


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
    assert document.local_path and Path(document.local_path).exists(), "live arxiv fetch did not persist local text file"
    print("[PASS] stage5::live_fetch_smoke")


def main() -> None:
    assert_stage5_local_fulltext_validation()
    print("[PASS] stage5::local_fulltext_validation")
    maybe_run_live_fetch_smoke()
    print("stage5 validation passed")


if __name__ == "__main__":
    main()
