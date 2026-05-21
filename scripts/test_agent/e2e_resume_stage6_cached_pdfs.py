"""Resume live analysis from cached Stage 5 PDFs and rerun Stage 6/7."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.analyzer.resolve import resolve_target_paper_metadata
from packages.author_intel import analyze_author_intel_with_live_clients
from packages.citation_sources.clients.semantic_scholar import SemanticScholarClient
from packages.citation_sources.models import CitingPaper
from packages.citation_sources.service import fetch_citation_candidates
from packages.reporting import build_report_artifact
from packages.sentiment import FullTextDocument, analyze_citation_sentiments
from packages.sentiment.fulltext import PDF_ARTIFACT_TEXT
from packages.shared.models import AuthorSummary, TargetPaper
from packages.shared.runtime_logging import AnalysisRuntimeOptions, RuntimeLogger, RuntimeLogMode, runtime_context


DEFAULT_TARGET = "https://arxiv.org/pdf/2507.19457"
DEFAULT_CACHE_DIR = REPO_ROOT / "downloaded-papers" / "stage5"


class NoopCrossrefClient:
    """Keep Semantic Scholar records as-is when resuming from cached PDFs."""

    def enrich_candidate(self, candidate: dict[str, object]) -> dict[str, object]:
        """Return Semantic Scholar candidate metadata without Crossref enrichment."""
        return candidate


def main() -> None:
    """Run Stage 6/7 using existing local PDFs instead of re-downloading them."""
    parser = argparse.ArgumentParser(description="Resume Stage 6/7 from cached Stage 5 PDF artifacts.")
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--max-citations", type=int, default=10000)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--log", choices=("quiet", "brief", "detail"), default="detail")
    parser.add_argument(
        "--skip-author-intel",
        action="store_true",
        help="Skip Stage 4 so Stage 6/7 can be rerun quickly from cached PDFs. Scholar and map sections will be empty.",
    )
    args = parser.parse_args()

    logger = RuntimeLogger(component="resume-stage6", mode=args.log)  # type: ignore[arg-type]
    with runtime_context(logger=logger, options=AnalysisRuntimeOptions(max_citations=args.max_citations)):
        target_paper = _resolve_target(args.target)
        logger.stage_done(
            "stage1",
            "目标论文元数据解析完成",
            title=target_paper.title,
            canonical_id=target_paper.canonical_id,
        )

        logger.stage_start("stage2", "轻量重建施引文献清单（跳过 Crossref 补全）")
        fetch_result = fetch_citation_candidates(
            target_paper=target_paper,
            semantic_scholar_client=SemanticScholarClient(),
            crossref_client=NoopCrossrefClient(),
            max_results=args.max_citations,
        )
        citing_papers = fetch_result.citing_papers
        logger.stage_done(
            "stage2",
            "施引文献清单重建完成",
            semantic=fetch_result.fetch_summary.semantic_scholar_candidates,
            deduped=fetch_result.fetch_summary.deduped_candidates,
        )

        if args.skip_author_intel:
            logger.skip(
                "stage4",
                "按参数跳过作者画像，直接复用本地 PDF 进入 Stage 6",
                reason="skip_author_intel",
            )
            author_profiles = []
            scholar_labels = []
            author_summary = AuthorSummary()
            author_errors = []
            skipped_papers = [
                {
                    "citing_paper_id": paper.canonical_id,
                    "title": paper.title,
                    "reason": "stage4_skipped_for_stage6_resume",
                    "paper_match_confidence": "not_attempted",
                    "openalex_work_status": "not_attempted",
                    "author_resolution_status": "not_attempted",
                    "selected_work_id": "",
                }
                for paper in citing_papers
            ]
        else:
            logger.stage_start("stage4", "查询施引作者画像")
            author_result = analyze_author_intel_with_live_clients(citing_papers)
            author_profiles = author_result.author_profiles
            scholar_labels = author_result.scholar_labels
            author_summary = author_result.author_summary
            author_errors = author_result.errors
            skipped_papers = author_result.skipped_papers
            logger.stage_done(
                "stage4",
                "作者画像完成",
                authors=len(author_profiles),
                matched=author_summary.matched_profiles,
                heavyweight=author_summary.heavyweight_candidates,
                high_impact=author_summary.high_impact_candidates,
                skipped=len(skipped_papers),
            )

        logger.stage_start("stage5", "复用本地 PDF 缓存")
        fulltext_documents = load_cached_pdf_documents(citing_papers, args.cache_dir)
        missing_pdf_errors = [
            f"stage5-cache:{paper.canonical_id}:missing_pdf"
            for paper in citing_papers
            if paper.canonical_id not in fulltext_documents
        ]
        logger.stage_done(
            "stage5",
            "本地 PDF 缓存装载完成",
            available=len(fulltext_documents),
            missing=len(citing_papers) - len(fulltext_documents),
        )

        logger.stage_start("stage6", "提取引用上下文并判断情感（禁用网络下载）")
        sentiment_result = analyze_citation_sentiments(
            target_paper=target_paper,
            citing_papers=citing_papers,
            fulltext_documents=fulltext_documents,
            allow_network=False,
            search_arxiv_fallback=False,
        )
        logger.stage_done(
            "stage6",
            "情感分析完成",
            positive=sentiment_result.summary.label_counts.get("positive", 0),
            neutral=sentiment_result.summary.label_counts.get("neutral", 0),
            critical=sentiment_result.summary.label_counts.get("critical", 0),
            unknown=sentiment_result.summary.label_counts.get("unknown", 0),
        )

        logger.stage_start("stage7", "生成 HTML / JSON / PDF 报告")
        artifact = build_report_artifact(
            target_paper=target_paper,
            citing_papers=citing_papers,
            author_profiles=author_profiles,
            scholar_labels=scholar_labels,
            author_summary=author_summary,
            citation_contexts=sentiment_result.contexts,
            sentiment_summary=sentiment_result.summary,
            fetch_summary=fetch_result.fetch_summary,
            source_trace=fetch_result.source_trace,
            state_errors=[*fetch_result.errors, *author_errors, *missing_pdf_errors],
            author_identity_skipped_papers=skipped_papers,
        )
        logger.stage_done(
            "stage7",
            "报告生成完成",
            html=artifact.export_paths.get("html"),
            json=artifact.export_paths.get("json"),
            pdf=artifact.export_paths.get("pdf"),
        )
        logger.summary(
            target=target_paper.canonical_id or target_paper.title,
            citing_papers=f"{len(citing_papers)} 篇",
            author_profiles=f"{len(author_profiles)} 位作者",
            fulltext=f"{len(fulltext_documents)}/{len(citing_papers)}",
            sentiment=(
                f"中性 {sentiment_result.summary.label_counts.get('neutral', 0)} / "
                f"正向 {sentiment_result.summary.label_counts.get('positive', 0)} / "
                f"批评 {sentiment_result.summary.label_counts.get('critical', 0)} / "
                f"未知 {sentiment_result.summary.label_counts.get('unknown', 0)}"
            ),
            report=artifact.export_paths.get("html", ""),
            status="report_generated",
        )
        print(
            f"✅ DONE e2e_resume_stage6_cached_pdfs | html={artifact.export_paths.get('html')} "
            f"json={artifact.export_paths.get('json')} pdf={artifact.export_paths.get('pdf')}",
            flush=True,
        )


def _resolve_target(target: str) -> TargetPaper:
    """Resolve target paper metadata from DOI, arXiv URL, or arXiv identifier."""
    arxiv_id = _extract_arxiv_id(target)
    if arxiv_id:
        return resolve_target_paper_metadata(
            TargetPaper(
                canonical_id=arxiv_id,
                paper_query=arxiv_id,
                paper_query_type="arxiv",
                source_ids={"arxiv": arxiv_id},
            )
        )
    return resolve_target_paper_metadata(
        TargetPaper(
            canonical_id=target,
            paper_query=target,
            paper_query_type="title",
        )
    )


def _extract_arxiv_id(value: str) -> str | None:
    """Extract an arXiv identifier from common arXiv URL shapes."""
    match = re.search(r"arxiv\.org/(?:abs|pdf)/([^?#]+)", value, flags=re.I)
    raw = match.group(1) if match else value
    raw = raw.strip().removesuffix(".pdf")
    if re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", raw):
        return raw
    return None


def load_cached_pdf_documents(
    citing_papers: list[CitingPaper],
    cache_dir: Path,
) -> dict[str, FullTextDocument]:
    """Build FullTextDocument objects from existing Stage 5 source.pdf files."""
    documents: dict[str, FullTextDocument] = {}
    for paper in citing_papers:
        pdf_path = find_cached_pdf(cache_dir, paper.canonical_id)
        if pdf_path is None:
            continue
        documents[paper.canonical_id] = FullTextDocument(
            citing_paper_id=paper.canonical_id,
            text=PDF_ARTIFACT_TEXT,
            source_type="pdf",
            source_label=str(pdf_path),
            local_path=str(pdf_path),
            raw_path=str(pdf_path),
            extracted_dir=str(pdf_path.parent),
            evidence_note="pdf_loaded_from_stage5_cache",
        )
    return documents


def find_cached_pdf(cache_dir: Path, citing_paper_id: str) -> Path | None:
    """Find the cached source.pdf for a citing-paper id."""
    matches = sorted(
        cache_dir.glob(f"{citing_paper_id}__*/source.pdf"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


if __name__ == "__main__":
    main()
