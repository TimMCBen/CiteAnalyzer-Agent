from __future__ import annotations

from typing import Protocol

from packages.author_intel.models import AuthorIntelResult
from packages.author_intel.normalize import build_author_candidates
from packages.author_intel.rules import build_scholar_label
from packages.citation_sources.models import CitingPaper
from packages.shared.models import AnalysisState, AuthorProfile, AuthorSummary
from packages.shared.runtime_logging import get_runtime_logger

AUTHOR_INTEL_NETWORK_FAILURE_BUDGET = 3


class OpenAlexClientProtocol(Protocol):
    def lookup_author(self, name: str) -> dict[str, object] | None:
        ...


class DBLPClientProtocol(Protocol):
    def lookup_author(self, name: str) -> dict[str, object] | None:
        ...


def analyze_author_intel(
    citing_papers: list[CitingPaper],
    openalex_client: OpenAlexClientProtocol,
    dblp_client: DBLPClientProtocol,
) -> AuthorIntelResult:
    candidates = build_author_candidates(citing_papers)
    result = AuthorIntelResult()
    network_failures = 0
    budget_warning_emitted = False
    matched_profiles = 0
    weak_signals = 0
    logger = get_runtime_logger()

    for index, candidate in enumerate(candidates, start=1):
        errors: list[str] = []
        openalex_record = None
        dblp_record = None

        if network_failures >= AUTHOR_INTEL_NETWORK_FAILURE_BUDGET:
            if not budget_warning_emitted:
                get_runtime_logger().warn(
                    "author_intel.retry_budget",
                    "作者画像网络查询累计失败较多，后续作者将直接降级为弱证据",
                    failures=network_failures,
                    impact="remaining_authors",
                )
                result.errors.append(f"author_intel_retry_budget_exhausted:failures={network_failures}")
                budget_warning_emitted = True
            profile = _build_profile(candidate.display_name, candidate.normalized_name, None, None)
            label = build_scholar_label(profile, candidate.frequency)
            result.author_profiles.append(profile)
            result.scholar_labels.append(label)
            weak_signals += 1
            logger.progress(
                "stage4",
                "作者画像",
                completed=index,
                total=len(candidates),
                current=candidate.display_name,
                status="skipped_budget",
                matched=matched_profiles,
                weak=weak_signals,
                failed=network_failures,
                remaining=len(candidates) - index,
            )
            continue

        try:
            openalex_record = openalex_client.lookup_author(candidate.display_name)
        except Exception as exc:  # pragma: no cover - network failure path
            network_failures += 1
            errors.append(f"openalex:{candidate.display_name}:{exc}")
            get_runtime_logger().warn(
                "openalex.lookup",
                "OpenAlex 查询作者时连接或服务异常，已降级为弱证据",
                author=candidate.display_name,
                error_type=exc.__class__.__name__,
                impact="single_author",
            )

        if _needs_dblp_fallback(openalex_record):
            try:
                dblp_record = dblp_client.lookup_author(candidate.display_name)
            except Exception as exc:  # pragma: no cover - network failure path
                network_failures += 1
                errors.append(f"dblp:{candidate.display_name}:{exc}")
                get_runtime_logger().warn(
                    "dblp.lookup",
                    "DBLP 查询作者失败，保留已有弱证据",
                    author=candidate.display_name,
                    error_type=exc.__class__.__name__,
                    impact="single_author",
                )

        profile = _build_profile(candidate.display_name, candidate.normalized_name, openalex_record, dblp_record)
        label = build_scholar_label(profile, candidate.frequency)

        result.author_profiles.append(profile)
        result.scholar_labels.append(label)
        result.errors.extend(errors)
        if profile.evidence_sources:
            matched_profiles += 1
        if label.label == "weak_signal_candidate":
            weak_signals += 1
        logger.progress(
            "stage4",
            "作者画像",
            completed=index,
            total=len(candidates),
            current=candidate.display_name,
            status=_progress_status(profile, label, errors),
            matched=matched_profiles,
            weak=weak_signals,
            failed=network_failures,
            remaining=len(candidates) - index,
        )

    result.author_summary = _build_summary(result.author_profiles, result.scholar_labels)
    return result


def analyze_author_intel_with_live_clients(citing_papers: list[CitingPaper]) -> AuthorIntelResult:
    from packages.author_intel.clients import DBLPClient, OpenAlexClient

    return analyze_author_intel(
        citing_papers=citing_papers,
        openalex_client=OpenAlexClient(),
        dblp_client=DBLPClient(),
    )


def attach_author_intel_result_to_state(state: AnalysisState, result: AuthorIntelResult) -> AnalysisState:
    state["author_profiles"] = result.author_profiles  # type: ignore[assignment]
    state["scholar_labels"] = result.scholar_labels  # type: ignore[assignment]
    state["author_summary"] = result.author_summary  # type: ignore[assignment]
    if result.errors:
        state.setdefault("errors", [])
        state["errors"].extend(result.errors)
    state["status"] = "author_intel_analyzed"
    return state


def _needs_dblp_fallback(openalex_record: dict[str, object] | None) -> bool:
    if openalex_record is None:
        return True
    return openalex_record.get("h_index") is None


def _build_profile(
    display_name: str,
    normalized_name: str,
    openalex_record: dict[str, object] | None,
    dblp_record: dict[str, object] | None,
) -> AuthorProfile:
    source_ids: dict[str, str] = {}
    evidence_sources: list[str] = []
    affiliations: list[str] = []
    fields: list[str] = []
    h_index = None
    citation_count = None
    works_count = None

    author_id = normalized_name
    name = display_name

    if openalex_record:
        author_id = str(openalex_record.get("author_id") or author_id)
        name = str(openalex_record.get("name") or name)
        source_ids.update({str(k): str(v) for k, v in dict(openalex_record.get("source_ids") or {}).items() if v})
        evidence_sources.extend([str(item) for item in list(openalex_record.get("evidence_sources") or []) if item])
        affiliations.extend([str(item) for item in list(openalex_record.get("affiliations") or []) if item])
        fields.extend([str(item) for item in list(openalex_record.get("fields") or []) if item])
        h_index = _coerce_optional_int(openalex_record.get("h_index"))
        citation_count = _coerce_optional_int(openalex_record.get("citation_count"))
        works_count = _coerce_optional_int(openalex_record.get("works_count"))

    if dblp_record:
        if not source_ids.get("dblp"):
            source_ids.update({str(k): str(v) for k, v in dict(dblp_record.get("source_ids") or {}).items() if v})
        for evidence_source in list(dblp_record.get("evidence_sources") or []):
            source_name = str(evidence_source)
            if source_name and source_name not in evidence_sources:
                evidence_sources.append(source_name)
        if not affiliations:
            affiliations.extend([str(item) for item in list(dblp_record.get("affiliations") or []) if item])
        if not fields:
            fields.extend([str(item) for item in list(dblp_record.get("fields") or []) if item])
        if not source_ids and dblp_record.get("author_id"):
            author_id = str(dblp_record["author_id"])

    deduped_affiliations = sorted(set(affiliations))
    deduped_fields = sorted(set(fields))
    deduped_sources = sorted(set(evidence_sources))

    return AuthorProfile(
        author_id=author_id,
        name=name,
        source_ids=source_ids,
        affiliations=deduped_affiliations,
        fields=deduped_fields,
        h_index=h_index,
        citation_count=citation_count,
        works_count=works_count,
        evidence_sources=deduped_sources,
    )


def _build_summary(author_profiles: list[AuthorProfile], scholar_labels: list) -> AuthorSummary:
    summary = AuthorSummary(total_authors=len(author_profiles))
    summary.matched_profiles = sum(1 for profile in author_profiles if profile.evidence_sources)
    summary.high_impact_candidates = sum(1 for label in scholar_labels if label.label == "high_impact_candidate")
    summary.heavyweight_candidates = sum(1 for label in scholar_labels if label.label == "heavyweight_candidate")
    summary.weak_signal_candidates = sum(1 for label in scholar_labels if label.label == "weak_signal_candidate")
    return summary


def _progress_status(profile: AuthorProfile, label: object, errors: list[str]) -> str:
    if errors:
        return "failed_lookup"
    if getattr(label, "label", None) == "weak_signal_candidate":
        return "weak_signal"
    if profile.evidence_sources:
        return "matched"
    return "weak_signal"


def _coerce_optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except ValueError:
            return None
    return None
