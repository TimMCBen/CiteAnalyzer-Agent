"""Resume final reporting by rerunning Stage 4 from an existing Stage 6 report."""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.analyzer.resolve import resolve_target_paper_metadata
from packages.author_intel import analyze_author_intel
from packages.citation_sources.clients.semantic_scholar import SemanticScholarClient
from packages.citation_sources.models import CitingPaper, FetchSummary, SourceTrace
from packages.citation_sources.service import fetch_citation_candidates
from packages.paper_identity.clients.arxiv import ArxivMetadataClient
from packages.paper_identity.clients.openalex_work import OpenAlexWorkClient
from packages.paper_identity.models import CandidateAuthor, CandidateWork
from packages.reporting import build_report_artifact
from packages.sentiment.models import CitationContext, SentimentSummary
from packages.shared.models import TargetPaper
from packages.shared.runtime_logging import AnalysisRuntimeOptions, RuntimeLogger, runtime_context


DEFAULT_TARGET = "https://arxiv.org/pdf/2507.19457"
DEFAULT_STAGE6_REPORT = REPO_ROOT / "generated-reports" / "2507-19457" / "report.json"
DEFAULT_STAGE4_CACHE = REPO_ROOT / "downloaded-papers" / "stage4-cache" / "openalex-work-author-cache.json"


class NoopCrossrefClient:
    """Keep Semantic Scholar citation records unchanged during resume runs."""

    def enrich_candidate(self, candidate: dict[str, object]) -> dict[str, object]:
        """Return Semantic Scholar candidate metadata without Crossref enrichment."""
        return candidate


class NoopArxivMetadataClient:
    """Skip arXiv identity lookups when OpenAlex work evidence is enough for Stage 4."""

    def lookup_ids(self, arxiv_ids: list[str]) -> list[CandidateWork]:
        """Return no direct arXiv ID candidates for the resume path."""
        return []

    def search_by_title(self, title: str, *, max_results: int = 3) -> list[CandidateWork]:
        """Return no arXiv title candidates for the resume path."""
        return []


class PersistentOpenAlexWorkClient:
    """Add a small JSON disk cache around OpenAlex work and author lookups."""

    def __init__(
        self,
        cache_path: Path,
        *,
        author_profile_limit: int = 0,
    ) -> None:
        self._client = OpenAlexWorkClient()
        self._cache_path = cache_path
        self._author_profile_limit = max(0, author_profile_limit)
        self._cache: dict[str, Any] = self._load_cache()
        self.cache_hits = 0
        self.cache_misses = 0
        self.author_network_lookups = 0
        self.author_limit_skips = 0

    @property
    def request_count(self) -> int:
        return self._client.request_count

    @property
    def http_attempt_count(self) -> int:
        return self._client.http_attempt_count

    def lookup_work_by_doi(self, doi: str | None) -> CandidateWork | None:
        """Resolve an OpenAlex work by DOI with persistent cache reuse."""
        clean = _normalize_doi(doi)
        if not clean:
            return None
        key = f"work:doi:{clean}"
        cached = self._get_cached(key)
        if cached is not _CACHE_MISS:
            return _candidate_work_from_dict(cached)
        work = self._client.lookup_work_by_doi(doi)
        self._set_cached(key, _candidate_work_to_dict(work))
        return work

    def search_work_by_title(self, title: str, *, per_page: int = 3) -> list[CandidateWork]:
        """Search OpenAlex works by title with persistent cache reuse."""
        query = str(title or "").strip()
        if not query:
            return []
        key = f"work:title:{query.lower()}:per_page:{max(1, min(per_page, 10))}"
        cached = self._get_cached(key)
        if cached is not _CACHE_MISS:
            return [_candidate_work_from_dict(item) for item in list(cached or []) if item]
        works = self._client.search_work_by_title(query, per_page=per_page)
        self._set_cached(key, [_candidate_work_to_dict(work) for work in works])
        return works

    def lookup_author_by_id(self, author_id: str | None) -> dict[str, object] | None:
        """Resolve an OpenAlex author profile by ID with an optional live-call cap."""
        clean = _normalize_openalex_author_id(author_id)
        if not clean:
            return None
        key = f"author:{clean}"
        cached = self._get_cached(key)
        if cached is not _CACHE_MISS:
            return dict(cached) if isinstance(cached, dict) else None
        if self._author_profile_limit and self.author_network_lookups >= self._author_profile_limit:
            self.author_limit_skips += 1
            return None
        self.author_network_lookups += 1
        profile = self._client.lookup_author_by_id(clean)
        self._set_cached(key, dict(profile) if isinstance(profile, dict) else None)
        return profile

    def _load_cache(self) -> dict[str, Any]:
        """Load the JSON cache, tolerating missing or malformed cache files."""
        if not self._cache_path.exists():
            return {}
        try:
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _get_cached(self, key: str) -> Any:
        """Return a cached value or the sentinel while updating cache counters."""
        if key in self._cache:
            self.cache_hits += 1
            return self._cache[key]
        self.cache_misses += 1
        return _CACHE_MISS

    def _set_cached(self, key: str, value: Any) -> None:
        """Persist one cache entry immediately for resumable long runs."""
        self._cache[key] = value
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(json.dumps(self._cache, ensure_ascii=False, indent=2), encoding="utf-8")


class _CacheMiss:
    """Sentinel type for distinguishing missing cache entries from cached None."""
    pass


_CACHE_MISS = _CacheMiss()


def main() -> None:
    """Rerun Stage 4 and Stage 7 using a previously generated Stage 6 report."""
    parser = argparse.ArgumentParser(description="Resume Stage 4/7 from an existing Stage 6 report.json.")
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument(
        "--target-title",
        default=None,
        help="Optional trusted target title override for report-only resume runs.",
    )
    parser.add_argument("--stage6-report", type=Path, default=DEFAULT_STAGE6_REPORT)
    parser.add_argument("--max-citations", type=int, default=10000)
    parser.add_argument("--log", choices=("quiet", "brief", "detail"), default="detail")
    parser.add_argument("--stage4-cache", type=Path, default=DEFAULT_STAGE4_CACHE)
    parser.add_argument(
        "--use-arxiv-identity-check",
        action="store_true",
        help="Also query arXiv during Stage 4 paper identity checks. Disabled by default to avoid arXiv 429 when resuming reports.",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Allow generating an empty report. Intended only for contract debugging.",
    )
    parser.add_argument(
        "--author-profile-limit",
        type=int,
        default=0,
        help="Maximum uncached OpenAlex author profile lookups. 0 means no limit.",
    )
    args = parser.parse_args()

    logger = RuntimeLogger(component="resume-stage4-stage7", mode=args.log)  # type: ignore[arg-type]
    with runtime_context(logger=logger, options=AnalysisRuntimeOptions(max_citations=args.max_citations)):
        payload = _load_stage6_payload(args.stage6_report)
        target_paper = _resolve_target(args.target, payload, target_title=args.target_title)
        citing_papers = _load_citing_papers(payload, max_citations=args.max_citations)
        fetch_summary: FetchSummary | None = None
        source_trace: list[SourceTrace] | None = None
        if not citing_papers and _has_context_rows(payload):
            logger.stage_start("stage2", "Stage 6 快照缺少施引论文标题，重新从 Semantic Scholar 轻量重建清单")
            fetch_result = fetch_citation_candidates(
                target_paper=target_paper,
                semantic_scholar_client=SemanticScholarClient(),
                crossref_client=NoopCrossrefClient(),
                max_results=args.max_citations,
            )
            citing_papers = fetch_result.citing_papers
            fetch_summary = fetch_result.fetch_summary
            source_trace = fetch_result.source_trace
            logger.stage_done(
                "stage2",
                "施引文献清单重建完成",
                semantic=fetch_result.fetch_summary.semantic_scholar_candidates,
                deduped=fetch_result.fetch_summary.deduped_candidates,
            )
        if not citing_papers and not args.allow_empty:
            raise ValueError(
                f"Stage 6 report has no restorable citing papers: {args.stage6_report}. "
                "Refusing to overwrite the final report with an empty artifact."
            )
        sentiment_contexts = _load_citation_contexts(payload, citing_papers=citing_papers)
        sentiment_summary = _build_sentiment_summary(sentiment_contexts, total_candidates=len(citing_papers))
        if fetch_summary is None:
            fetch_summary = _build_fetch_summary(target_paper, len(citing_papers), payload)
        if source_trace is None:
            source_trace = _build_source_trace(citing_papers, target_paper)

        logger.stage_done(
            "stage1",
            "目标论文元数据解析完成",
            title=target_paper.title,
            canonical_id=target_paper.canonical_id,
            arxiv=target_paper.source_ids.get("arxiv"),
        )
        logger.stage_done(
            "stage6.restore",
            "已从既有 report.json 恢复 Stage 6 结果",
            contexts=len(sentiment_contexts),
            context_found=sentiment_summary.context_found,
            positive=sentiment_summary.label_counts.get("positive", 0),
            neutral=sentiment_summary.label_counts.get("neutral", 0),
            critical=sentiment_summary.label_counts.get("critical", 0),
            unknown=sentiment_summary.label_counts.get("unknown", 0),
        )

        logger.stage_start("stage4", "使用 OpenAlex work-authorship 重建作者画像")
        openalex_client = PersistentOpenAlexWorkClient(
            args.stage4_cache,
            author_profile_limit=args.author_profile_limit,
        )
        author_result = analyze_author_intel(
            citing_papers=citing_papers,
            openalex_client=openalex_client,
            arxiv_client=ArxivMetadataClient() if args.use_arxiv_identity_check else NoopArxivMetadataClient(),
        )
        author_errors = list(author_result.errors)
        if args.author_profile_limit and openalex_client.author_limit_skips:
            author_errors.append(
                f"stage4_author_profile_limit_reached:"
                f"limit={args.author_profile_limit},skipped={openalex_client.author_limit_skips}"
            )
        logger.stage_done(
            "stage4",
            "作者画像完成",
            authors=len(author_result.author_profiles),
            matched=author_result.author_summary.matched_profiles,
            heavyweight=author_result.author_summary.heavyweight_candidates,
            high_impact=author_result.author_summary.high_impact_candidates,
            skipped_papers=len(author_result.skipped_papers),
            cache_hits=openalex_client.cache_hits,
            cache_misses=openalex_client.cache_misses,
            openalex_requests=openalex_client.request_count,
            author_limit_skips=openalex_client.author_limit_skips,
        )

        logger.stage_start("stage7", "重新生成 HTML / JSON / PDF 展示报告")
        artifact = build_report_artifact(
            target_paper=target_paper,
            citing_papers=citing_papers,
            author_profiles=author_result.author_profiles,
            scholar_labels=author_result.scholar_labels,
            author_summary=author_result.author_summary,
            citation_contexts=sentiment_contexts,
            sentiment_summary=sentiment_summary,
            fetch_summary=fetch_summary,
            source_trace=source_trace,
            state_errors=author_errors,
            author_identity_skipped_papers=author_result.skipped_papers,
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
            author_profiles=f"{len(author_result.author_profiles)} 位作者",
            author_skipped=f"{len(author_result.skipped_papers)} 篇施引论文",
            cache=f"hit {openalex_client.cache_hits} / miss {openalex_client.cache_misses}",
            sentiment=(
                f"中性 {sentiment_summary.label_counts.get('neutral', 0)} / "
                f"正向 {sentiment_summary.label_counts.get('positive', 0)} / "
                f"批评 {sentiment_summary.label_counts.get('critical', 0)} / "
                f"未知 {sentiment_summary.label_counts.get('unknown', 0)}"
            ),
            report=artifact.export_paths.get("html", ""),
            pdf=artifact.export_paths.get("pdf", ""),
            status="report_generated",
        )
        print(
            f"✅ DONE e2e_resume_stage4_stage7_from_report | html={artifact.export_paths.get('html')} "
            f"json={artifact.export_paths.get('json')} pdf={artifact.export_paths.get('pdf')}",
            flush=True,
        )


def _load_stage6_payload(path: Path) -> dict[str, Any]:
    """Read and validate the Stage 6 JSON report payload."""
    if not path.exists():
        raise FileNotFoundError(f"Stage 6 report not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Stage 6 report is not a JSON object: {path}")
    return payload


def _has_context_rows(payload: dict[str, Any]) -> bool:
    return any(isinstance(item, dict) for item in list(payload.get("contexts") or []))


def _resolve_target(target: str, payload: dict[str, Any], *, target_title: str | None = None) -> TargetPaper:
    """Resolve target metadata, falling back to report payload fields offline."""
    arxiv_id = _extract_arxiv_id(target) or str(payload.get("summary", {}).get("target_arxiv_id") or "")
    clean_target_title = str(target_title or "").strip()
    try:
        if arxiv_id:
            resolved = resolve_target_paper_metadata(
                TargetPaper(
                    canonical_id=arxiv_id,
                    paper_query=arxiv_id,
                    paper_query_type="arxiv",
                    source_ids={"arxiv": arxiv_id},
                )
            )
            if clean_target_title:
                resolved.title = clean_target_title
            return resolved
        resolved = resolve_target_paper_metadata(
            TargetPaper(canonical_id=target, paper_query=target, paper_query_type="title")
        )
        if clean_target_title:
            resolved.title = clean_target_title
        return resolved
    except Exception:
        summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
        return TargetPaper(
            canonical_id=arxiv_id or str(summary.get("target_title") or target),
            paper_query=target,
            paper_query_type="arxiv" if arxiv_id else "title",
            title=clean_target_title or str(summary.get("target_title") or target),
            doi=str(summary.get("target_doi") or "").strip() or None,
            source_ids={"arxiv": arxiv_id} if arxiv_id else {},
            resolve_status="uncertain",
        )


def _load_citing_papers(payload: dict[str, Any], *, max_citations: int) -> list[CitingPaper]:
    """Reconstruct unique citing-paper records from saved context rows."""
    contexts = list(payload.get("contexts") or [])
    papers: list[CitingPaper] = []
    seen: set[str] = set()
    for item in contexts:
        if not isinstance(item, dict):
            continue
        paper_id = str(item.get("citing_paper_id") or "").strip()
        title = str(item.get("citing_paper_title") or "").strip()
        if not paper_id or paper_id in seen or not title:
            continue
        papers.append(
            CitingPaper(
                canonical_id=paper_id,
                title=title,
                doi=str(item.get("citing_paper_doi") or "").strip() or None,
                year=_coerce_int(item.get("citing_paper_year")),
                source_names=["semantic_scholar", "stage6_report"],
            )
        )
        seen.add(paper_id)
        if len(papers) >= max_citations:
            break
    return papers


def _load_citation_contexts(payload: dict[str, Any], *, citing_papers: list[CitingPaper]) -> list[CitationContext]:
    """Restore citation-context rows for the selected citing-paper subset."""
    allowed_ids = {paper.canonical_id for paper in citing_papers}
    contexts: list[CitationContext] = []
    for item in list(payload.get("contexts") or []):
        if not isinstance(item, dict):
            continue
        paper_id = str(item.get("citing_paper_id") or "").strip()
        if paper_id not in allowed_ids:
            continue
        label = str(item.get("sentiment_label") or "unknown").strip()
        if label not in {"positive", "neutral", "critical", "unknown"}:
            label = "unknown"
        contexts.append(
            CitationContext(
                citing_paper_id=paper_id,
                sentiment_label=label,  # type: ignore[arg-type]
                context_text=str(item.get("context_text") or "").strip() or None,
                matched_target_reference=str(item.get("matched_target_reference") or "").strip() or None,
                evidence_note=str(item.get("evidence_note") or "").strip() or "restored_from_stage6_report",
                text_source_type=_safe_text_source_type(item.get("text_source_type")),
                text_source_label=str(item.get("text_source_label") or "").strip() or None,
            )
        )
    return contexts


def _build_sentiment_summary(contexts: list[CitationContext], *, total_candidates: int) -> SentimentSummary:
    """Recalculate sentiment aggregate counts from restored contexts."""
    summary = SentimentSummary(total_candidates=total_candidates)
    summary.fulltext_available = sum(1 for context in contexts if context.text_source_type == "pdf")
    summary.context_found = sum(1 for context in contexts if context.context_text)
    for context in contexts:
        summary.label_counts[context.sentiment_label] += 1
    summary.unknown_count = summary.label_counts["unknown"]
    summary.classified_count = total_candidates - summary.unknown_count
    return summary


def _build_fetch_summary(target_paper: TargetPaper, citing_count: int, payload: dict[str, Any]) -> FetchSummary:
    """Build a provenance summary for report-only resume output."""
    provenance = payload.get("provenance", {}) if isinstance(payload.get("provenance"), dict) else {}
    notes = [str(note) for note in list(provenance.get("fetch_notes") or []) if note]
    notes.append("stage4_stage7_resumed_from_existing_stage6_report")
    return FetchSummary(
        target_query=target_paper.paper_query or target_paper.canonical_id or "",
        target_title=target_paper.title,
        target_doi=target_paper.doi,
        target_resolve_status=target_paper.resolve_status,
        semantic_scholar_candidates=citing_count,
        merged_candidates=citing_count,
        deduped_candidates=citing_count,
        partial_failure=bool(provenance.get("partial_failure")),
        notes=notes,
    )


def _build_source_trace(citing_papers: list[CitingPaper], target_paper: TargetPaper) -> list[SourceTrace]:
    """Create synthetic source-trace rows for records restored from a report."""
    fetched_at = datetime.now(timezone.utc).isoformat()
    query = target_paper.canonical_id or target_paper.title or ""
    return [
        SourceTrace(
            candidate_id=paper.canonical_id,
            source_name="stage6_report",
            source_record_id=paper.canonical_id,
            query_used=query,
            fetched_at=fetched_at,
            raw_title=paper.title,
            raw_doi=paper.doi,
            merge_status="restored",
        )
        for paper in citing_papers
    ]


def _candidate_work_to_dict(work: CandidateWork | None) -> dict[str, Any] | None:
    return asdict(work) if work else None


def _candidate_work_from_dict(value: Any) -> CandidateWork | None:
    """Restore a CandidateWork dataclass from a cache dictionary."""
    if not isinstance(value, dict):
        return None
    authors = [
        CandidateAuthor(**author)
        for author in list(value.get("authors") or [])
        if isinstance(author, dict)
    ]
    data = dict(value)
    data["authors"] = authors
    return CandidateWork(**data)


def _extract_arxiv_id(value: str) -> str | None:
    """Extract an arXiv ID from a URL or bare ID string."""
    match = re.search(r"arxiv\.org/(?:abs|pdf)/([^?#]+)", value, flags=re.I)
    raw = match.group(1) if match else value
    raw = raw.strip().removesuffix(".pdf")
    if re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", raw):
        return raw
    return None


def _normalize_doi(doi: str | None) -> str | None:
    """Normalize DOI strings and DOI URLs for stable cache keys."""
    if not doi:
        return None
    text = str(doi).strip()
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text, flags=re.IGNORECASE)
    return text.lower() or None


def _normalize_openalex_author_id(author_id: str | None) -> str | None:
    """Normalize OpenAlex author IDs to the compact A-number form."""
    if not author_id:
        return None
    match = re.search(r"A\d+", str(author_id), flags=re.IGNORECASE)
    return match.group(0).upper() if match else None


def _coerce_int(value: Any) -> int | None:
    """Convert report JSON year-like values to integers when possible."""
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _safe_text_source_type(value: Any) -> str:
    """Clamp restored text source types to the sentiment model enum."""
    text = str(value or "unknown")
    if text in {"fulltext", "markdown", "pdf", "abstract", "unknown"}:
        return text
    return "unknown"


if __name__ == "__main__":
    main()
