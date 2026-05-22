"""Author-intelligence service for work-authorship-based author profiling."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from packages.author_intel.models import AuthorIntelResult
from packages.author_intel.rules import build_scholar_label
from packages.citation_sources.models import CitingPaper
from packages.paper_identity.models import CandidateAuthor, PaperIdentityDecision
from packages.paper_identity.service import resolve_paper_identity
from packages.shared.models import AnalysisState, AuthorProfile, AuthorSummary
from packages.shared.runtime_logging import get_runtime_logger


class OpenAlexWorkAuthorClientProtocol(Protocol):
    """OpenAlex work/author client required by work-authorship Stage 4."""
    def lookup_work_by_doi(self, doi: str | None):
        ...

    def search_work_by_title(self, title: str, *, per_page: int = 3):
        ...

    def lookup_author_by_id(self, author_id: str | None) -> dict[str, object] | None:
        ...


class ArxivMetadataClientProtocol(Protocol):
    """arXiv metadata client required by paper identity resolution."""
    def lookup_ids(self, arxiv_ids: list[str]):
        ...

    def search_by_title(self, title: str, *, max_results: int = 3):
        ...


@dataclass
class _AuthorAccumulator:
    """Accumulate trusted work-authorship evidence before building profiles."""
    author: CandidateAuthor
    citing_ids: set[str] = field(default_factory=set)
    institutions: set[str] = field(default_factory=set)
    countries: set[str] = field(default_factory=set)
    decision_statuses: set[str] = field(default_factory=set)


def analyze_author_intel(
    citing_papers: list[CitingPaper],
    openalex_client: OpenAlexWorkAuthorClientProtocol,
    arxiv_client: ArxivMetadataClientProtocol,
    *,
    use_llm_review: bool = False,
) -> AuthorIntelResult:
    """Build author profiles only from trusted OpenAlex work.authorships."""
    result = AuthorIntelResult()
    author_evidence: dict[str, _AuthorAccumulator] = {}
    logger = get_runtime_logger()

    for citing_paper in citing_papers:
        try:
            decision = resolve_paper_identity(
                citing_paper,
                openalex_client=openalex_client,
                arxiv_client=arxiv_client,
                use_llm_review=use_llm_review,
            )
        except Exception as exc:  # pragma: no cover - network failure path
            reason = f"identity_lookup_failed:{exc.__class__.__name__}"
            result.errors.append(f"author_intel_identity:{citing_paper.canonical_id}:{exc}")
            _record_skipped_paper(result, citing_paper, reason)
            logger.warn(
                "author_intel.paper_identity_skip",
                "施引论文身份解析失败，跳过作者画像",
                citing_paper_id=citing_paper.canonical_id,
                error_type=exc.__class__.__name__,
                impact="single_paper",
            )
            continue

        result.identity_decisions[citing_paper.canonical_id] = decision
        if not _can_use_work_authorship(decision):
            reason = _skip_reason(decision)
            _record_skipped_paper(result, citing_paper, reason, decision)
            logger.warn(
                "author_intel.paper_identity_skip",
                "施引论文未达到 work-authorship 作者画像条件，跳过作者画像",
                citing_paper_id=citing_paper.canonical_id,
                reason=reason,
                confidence=decision.paper_match_confidence,
                work_status=decision.openalex_work_status,
                author_status=decision.author_resolution_status,
                impact="single_paper",
            )
            continue

        selected_work = decision.selected_work
        authors_with_ids = [author for author in selected_work.authors if author.author_id] if selected_work else []
        if not authors_with_ids:
            reason = "missing_work_author_ids"
            _record_skipped_paper(result, citing_paper, reason, decision)
            logger.warn(
                "author_intel.authorship_missing",
                "可信 OpenAlex work 缺少 authorship author_id，跳过作者画像",
                citing_paper_id=citing_paper.canonical_id,
                selected_work_id=selected_work.work_id if selected_work else None,
                impact="single_paper",
            )
            continue

        for author in authors_with_ids:
            key = str(author.author_id)
            accumulator = author_evidence.get(key)
            if accumulator is None:
                accumulator = _AuthorAccumulator(author=author)
                author_evidence[key] = accumulator
            accumulator.citing_ids.add(citing_paper.canonical_id)
            accumulator.institutions.update(author.institutions)
            accumulator.countries.update(author.countries)
            accumulator.decision_statuses.add(decision.author_resolution_status)

        logger.detail(
            "author_intel.work_authorship_used",
            "已采用 OpenAlex work.authorships 作为作者画像来源",
            citing_paper_id=citing_paper.canonical_id,
            authors=len(authors_with_ids),
            confidence=decision.paper_match_confidence,
        )

    sorted_author_evidence = sorted(author_evidence.items(), key=lambda item: item[0])
    matched_profiles = 0
    weak_signals = 0
    failed_lookups = 0
    for index, (author_id, accumulator) in enumerate(sorted_author_evidence, start=1):
        previous_error_count = len(result.errors)
        author_record = _lookup_author_profile_by_id(openalex_client, author_id, result)
        profile = _build_profile_from_work_authorship(accumulator, author_record)
        label = build_scholar_label(profile, len(accumulator.citing_ids))
        failed_lookup = len(result.errors) > previous_error_count
        result.author_profiles.append(profile)
        result.scholar_labels.append(label)
        if author_record:
            matched_profiles += 1
        if label.label == "weak_signal_candidate":
            weak_signals += 1
        if failed_lookup:
            failed_lookups += 1
        logger.progress(
            "stage4",
            "作者画像",
            completed=index,
            total=len(sorted_author_evidence),
            current=profile.name,
            status=_progress_status(author_record, label, failed_lookup),
            matched=matched_profiles,
            weak=weak_signals,
            failed=failed_lookups,
            remaining=len(sorted_author_evidence) - index,
        )

    result.author_summary = _build_summary(result.author_profiles, result.scholar_labels)
    logger.stage_done(
        "author_intel.work_authorship",
        "work-authorship 作者画像完成",
        profiles=len(result.author_profiles),
        skipped_papers=len(result.skipped_papers),
    )
    return result


def analyze_author_intel_with_live_clients(citing_papers: list[CitingPaper]) -> AuthorIntelResult:
    """Run author profiling with live OpenAlex work authorships and arXiv metadata."""
    from packages.paper_identity.clients.arxiv import ArxivMetadataClient
    from packages.paper_identity.clients.openalex_work import OpenAlexWorkClient

    return analyze_author_intel(
        citing_papers=citing_papers,
        openalex_client=OpenAlexWorkClient(),
        arxiv_client=ArxivMetadataClient(),
    )


def attach_author_intel_result_to_state(state: AnalysisState, result: AuthorIntelResult) -> AnalysisState:
    """Attach author profiles, labels, identity decisions, and errors to analyzer state."""
    state["author_profiles"] = result.author_profiles  # type: ignore[assignment]
    state["scholar_labels"] = result.scholar_labels  # type: ignore[assignment]
    state["author_summary"] = result.author_summary  # type: ignore[assignment]
    state["paper_identity_decisions"] = result.identity_decisions  # type: ignore[assignment]
    state["author_intel_skipped_papers"] = result.skipped_papers  # type: ignore[assignment]
    if result.errors:
        state.setdefault("errors", [])
        state["errors"].extend(result.errors)
    state["status"] = "author_intel_analyzed"
    return state


def _can_use_work_authorship(decision: PaperIdentityDecision) -> bool:
    """Return whether a paper identity decision is safe for author-id profiling."""
    return (
        decision.paper_match_confidence in {"high", "medium"}
        and decision.author_resolution_status in {"work_authorship_verified", "work_authorship_variant"}
        and decision.selected_work is not None
    )


def _skip_reason(decision: PaperIdentityDecision) -> str:
    """Create a compact skip reason from paper identity status fields."""
    if decision.selected_work is None:
        return f"no_selected_work:{decision.paper_match_confidence}"
    if decision.paper_match_confidence not in {"high", "medium"}:
        return f"paper_confidence_{decision.paper_match_confidence}"
    if decision.author_resolution_status not in {"work_authorship_verified", "work_authorship_variant"}:
        return f"author_resolution_{decision.author_resolution_status}"
    return "work_authorship_unusable"


def _record_skipped_paper(
    result: AuthorIntelResult,
    citing_paper: CitingPaper,
    reason: str,
    decision: PaperIdentityDecision | None = None,
) -> None:
    """Store a skipped citing-paper decision for logs and reports."""
    item = {
        "citing_paper_id": citing_paper.canonical_id,
        "title": citing_paper.title,
        "reason": reason,
    }
    if decision:
        item.update(
            {
                "paper_match_confidence": decision.paper_match_confidence,
                "openalex_work_status": decision.openalex_work_status,
                "author_resolution_status": decision.author_resolution_status,
                "selected_work_id": decision.selected_work.work_id if decision.selected_work else "",
            }
        )
    result.skipped_papers.append(item)


def _lookup_author_profile_by_id(
    openalex_client: OpenAlexWorkAuthorClientProtocol,
    author_id: str,
    result: AuthorIntelResult,
) -> dict[str, object] | None:
    """Fetch an OpenAlex author profile by id without falling back to name search."""
    try:
        return openalex_client.lookup_author_by_id(author_id)
    except Exception as exc:  # pragma: no cover - network failure path
        result.errors.append(f"openalex_author_id:{author_id}:{exc}")
        get_runtime_logger().warn(
            "openalex.author_id",
            "OpenAlex author_id 作者画像查询失败，保留 work-authorship 弱画像",
            author_id=author_id,
            error_type=exc.__class__.__name__,
            impact="single_author",
        )
        return None


def _build_profile_from_work_authorship(
    accumulator: _AuthorAccumulator,
    author_record: dict[str, object] | None,
) -> AuthorProfile:
    """Merge trusted work-authorship evidence with optional author-id metrics."""
    author = accumulator.author
    author_id = str(author.author_id or author.name)
    source_ids = {"openalex": author_id} if author.author_id else {}
    evidence_sources = ["openalex_work_authorship"]
    affiliations = set(accumulator.institutions)
    fields: set[str] = set()
    h_index = None
    citation_count = None
    works_count = None
    name = author.name or author.raw_author_name or author_id

    if author_record:
        name = str(author_record.get("name") or name)
        source_ids.update({str(k): str(v) for k, v in dict(author_record.get("source_ids") or {}).items() if v})
        evidence_sources.extend([str(item) for item in list(author_record.get("evidence_sources") or []) if item])
        affiliations.update(str(item) for item in list(author_record.get("affiliations") or []) if item)
        fields.update(str(item) for item in list(author_record.get("fields") or []) if item)
        h_index = _coerce_optional_int(author_record.get("h_index"))
        citation_count = _coerce_optional_int(author_record.get("citation_count"))
        works_count = _coerce_optional_int(author_record.get("works_count"))

    for status in sorted(accumulator.decision_statuses):
        evidence_sources.append(status)

    return AuthorProfile(
        author_id=author_id,
        name=name,
        source_ids=source_ids,
        affiliations=sorted(affiliations),
        countries=sorted(accumulator.countries),
        fields=sorted(fields),
        h_index=h_index,
        citation_count=citation_count,
        works_count=works_count,
        evidence_sources=sorted(set(evidence_sources)),
    )


def _build_summary(author_profiles: list[AuthorProfile], scholar_labels: list) -> AuthorSummary:
    """Summarize author profile coverage and high-impact labels."""
    summary = AuthorSummary(total_authors=len(author_profiles))
    summary.matched_profiles = sum(1 for profile in author_profiles if profile.evidence_sources)
    summary.high_impact_candidates = sum(1 for label in scholar_labels if label.label == "high_impact_candidate")
    summary.heavyweight_candidates = sum(1 for label in scholar_labels if label.label == "heavyweight_candidate")
    summary.weak_signal_candidates = sum(1 for label in scholar_labels if label.label == "weak_signal_candidate")
    return summary


def _progress_status(author_record: dict[str, object] | None, label: object, failed_lookup: bool) -> str:
    """Return a compact Stage 4 progress status."""
    if failed_lookup:
        return "failed_lookup"
    if getattr(label, "label", None) == "weak_signal_candidate":
        return "weak_signal"
    if author_record:
        return "matched"
    return "work_authorship"


def _coerce_optional_int(value: object) -> int | None:
    """Coerce optional numeric author metrics into integers."""
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except ValueError:
            return None
    return None
