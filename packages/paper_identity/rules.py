"""Rules helpers for paper identity matching."""
from __future__ import annotations

from packages.paper_identity.models import (
    CandidateWork,
    PaperIdentityDecision,
    PaperIdentityEvidence,
)
from packages.paper_identity.title_similarity import author_name_overlap, title_similarity


HIGH_TITLE_THRESHOLD = 0.95
VERIFIED_ID_TITLE_THRESHOLD = 0.90
MEDIUM_TITLE_THRESHOLD = 0.80


def decide_paper_identity(evidence: PaperIdentityEvidence) -> PaperIdentityDecision:
    """Choose the best paper identity decision from evidence for paper identity matching."""
    notes: list[str] = []
    conflicts: list[str] = []

    if evidence.errors and not any((evidence.doi_work, evidence.title_work_candidates, evidence.arxiv_candidates)):
        return PaperIdentityDecision(
            citing_paper_id=evidence.citing_paper_id,
            arxiv_status="lookup_failed" if any("arxiv" in error.lower() for error in evidence.errors) else "absent",
            doi_status="lookup_failed" if evidence.doi and any("doi" in error.lower() for error in evidence.errors) else ("present_unchecked" if evidence.doi else "absent"),
            openalex_work_status="lookup_failed",
            selected_work_source="unresolved",
            paper_match_confidence="error",
            author_resolution_status="lookup_failed",
            source_conflicts=list(evidence.errors),
            evidence_notes=["外部候选查询失败，不能让模型凭空判断论文身份。"],
            needs_llm_review=False,
        )

    doi_status = "absent"
    openalex_status = "not_attempted"
    arxiv_status = _arxiv_status_from_evidence(evidence)

    if evidence.doi:
        doi_status = "present_unchecked"

    selected_work: CandidateWork | None = None
    selected_source = "unresolved"
    confidence = "miss"
    selected_score: float | None = None

    if evidence.doi_work is not None:
        score = title_similarity(evidence.title, evidence.doi_work.title)
        selected_score = score
        if score >= VERIFIED_ID_TITLE_THRESHOLD and not _has_author_count_anomaly(evidence, evidence.doi_work):
            doi_status = "present_verified"
            openalex_status = "doi_hit_verified"
            selected_work = evidence.doi_work
            selected_source = "doi_verified"
            confidence = "high"
            notes.append(f"DOI 命中且标题相似度 {score:.3f} 达到高置信阈值。")
        elif score >= MEDIUM_TITLE_THRESHOLD:
            doi_status = "present_title_variant"
            openalex_status = "doi_hit_variant"
            selected_work = evidence.doi_work
            selected_source = "title_variant"
            confidence = "medium"
            notes.append(f"DOI 命中但标题相似度 {score:.3f} 处于中置信区间。")
        else:
            doi_status = "present_mismatch"
            openalex_status = "doi_hit_mismatch"
            conflicts.append("doi_title_mismatch")
            notes.append(f"DOI 命中标题相似度仅 {score:.3f}，疑似 DOI 指向其它论文。")

    title_best, title_score, title_source = _best_title_candidate(evidence)
    if title_best is not None:
        if title_score >= HIGH_TITLE_THRESHOLD:
            if selected_work is None or confidence in {"miss", "low", "medium"}:
                selected_work = title_best
                selected_score = title_score
                selected_source = "arxiv_verified" if title_source == "arxiv" else "openalex_title_verified"
                confidence = "high"
                if title_source == "openalex":
                    openalex_status = "title_hit_verified"
                    notes.append(f"标题搜索命中 OpenAlex work，标题相似度 {title_score:.3f}。")
                else:
                    if openalex_status == "not_attempted":
                        openalex_status = "no_result"
                    notes.append(f"arXiv 候选命中且标题相似度 {title_score:.3f}。")
        elif title_score >= MEDIUM_TITLE_THRESHOLD and selected_work is None:
            selected_work = title_best
            selected_score = title_score
            selected_source = "title_variant"
            confidence = "medium"
            if title_source == "openalex":
                openalex_status = "title_hit_variant"
                notes.append(f"OpenAlex 标题搜索候选相似度 {title_score:.3f}，需要 GPT 复核。")
            else:
                if openalex_status == "not_attempted":
                    openalex_status = "no_result"
                notes.append(f"arXiv 候选相似度 {title_score:.3f}，需要 GPT 复核。")
        elif selected_work is None:
            if title_source == "openalex":
                openalex_status = "title_hit_mismatch"
            elif openalex_status == "not_attempted":
                openalex_status = "no_result"
            confidence = "low"
            selected_score = title_score
            conflicts.append("title_search_mismatch")
            notes.append(f"标题搜索候选相似度仅 {title_score:.3f}。")

    if selected_work is None:
        if openalex_status == "not_attempted":
            openalex_status = "no_result"
        selected_source = "semantic_scholar_only" if evidence.title else "unresolved"
        confidence = "miss"
        notes.append("没有找到可信外部 work，保留 Semantic Scholar 原始记录。")

    if selected_work is not None and _has_author_count_anomaly(evidence, selected_work):
        conflicts.append("author_count_mismatch")
        notes.append(
            f"作者数差异较大：Semantic Scholar={len(evidence.authors)}, OpenAlex={len(selected_work.authors)}。"
        )
        if confidence == "high":
            confidence = "medium"

    if evidence.year and selected_work and selected_work.year and abs(evidence.year - selected_work.year) >= 3:
        conflicts.append("year_type_anomaly")
        notes.append(f"年份差异较大：Semantic Scholar={evidence.year}, OpenAlex={selected_work.year}。")
        if confidence == "high":
            confidence = "medium"

    needs_llm_review = confidence == "medium" or bool(conflicts and confidence != "low")
    author_status = _author_resolution_status(selected_work, confidence)

    return PaperIdentityDecision(
        citing_paper_id=evidence.citing_paper_id,
        arxiv_status=arxiv_status,
        doi_status=doi_status,  # type: ignore[arg-type]
        openalex_work_status=openalex_status,  # type: ignore[arg-type]
        selected_work_source=selected_source,  # type: ignore[arg-type]
        paper_match_confidence=confidence,  # type: ignore[arg-type]
        author_resolution_status=author_status,
        selected_work=selected_work,
        title_similarity=selected_score,
        source_conflicts=sorted(set(conflicts)),
        evidence_notes=notes,
        needs_llm_review=needs_llm_review,
    )


def merge_llm_review(decision: PaperIdentityDecision) -> PaperIdentityDecision:
    """Merge LLM review for paper identity matching."""
    review = decision.llm_review
    if review is None:
        return decision

    if decision.paper_match_confidence in {"error", "miss"}:
        decision.evidence_notes.append("硬约束：无候选或查询失败时 GPT 不能把结果提升为高置信。")
        return decision
    if decision.selected_work is None:
        decision.evidence_notes.append("硬约束：没有 selected_work 时 GPT 不能判 high。")
        return decision

    if review.paper_identity_decision == "same_paper" and review.paper_confidence == "high":
        if decision.title_similarity is not None and decision.title_similarity < MEDIUM_TITLE_THRESHOLD:
            decision.evidence_notes.append("硬约束：标题相似度低于中置信阈值，GPT 不能升到 high。")
            return decision
        decision.paper_match_confidence = "high"
        decision.needs_llm_review = False
        decision.evidence_notes.append(f"GPT 复核接受：{review.reason_zh}")
    elif review.paper_identity_decision == "different_paper":
        decision.paper_match_confidence = "low"
        decision.selected_work_source = "conflicting_sources"
        decision.author_resolution_status = "skipped_due_to_paper_mismatch"
        decision.evidence_notes.append(f"GPT 复核判定不是同一篇：{review.reason_zh}")
    else:
        decision.evidence_notes.append(f"GPT 复核仍不确定：{review.reason_zh}")
    return decision


def _best_title_candidate(evidence: PaperIdentityEvidence) -> tuple[CandidateWork | None, float, str | None]:
    """Select the strongest title-matched work candidate for paper identity matching."""
    candidates = [
        *((candidate, "openalex") for candidate in evidence.title_work_candidates),
        *((candidate, "arxiv") for candidate in evidence.arxiv_candidates),
    ]
    if not candidates:
        return None, 0.0, None
    scored = [(title_similarity(evidence.title, candidate.title), candidate, source) for candidate, source in candidates]
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1], scored[0][0], scored[0][2]


def _has_author_count_anomaly(evidence: PaperIdentityEvidence, candidate: CandidateWork) -> bool:
    """Return whether author count anomaly for paper identity matching."""
    source_count = len(evidence.authors)
    candidate_count = len(candidate.authors)
    if not source_count or not candidate_count:
        return False
    if author_name_overlap(evidence.authors, [author.name for author in candidate.authors]) >= 0.50:
        return False
    return abs(source_count - candidate_count) >= max(3, source_count // 2)


def _author_resolution_status(selected_work: CandidateWork | None, confidence: str):
    """Summarize author resolution confidence for a work for paper identity matching."""
    if selected_work is None:
        return "weak_signal_only"
    if not selected_work.author_ids:
        return "weak_signal_only"
    if confidence == "high":
        return "work_authorship_verified"
    if confidence == "medium":
        return "work_authorship_variant"
    return "skipped_due_to_paper_mismatch"


def _arxiv_status_from_evidence(evidence: PaperIdentityEvidence):
    """Derive arXiv verification status from identity evidence for paper identity matching."""
    if evidence.arxiv_candidates:
        best, score, _ = _best_title_candidate(
            PaperIdentityEvidence(
                citing_paper_id=evidence.citing_paper_id,
                title=evidence.title,
                arxiv_candidates=evidence.arxiv_candidates,
            )
        )
        if best and score >= HIGH_TITLE_THRESHOLD:
            return "present_verified"
        if best and score >= MEDIUM_TITLE_THRESHOLD:
            return "present_title_variant"
        return "present_mismatch"
    if evidence.arxiv_id_hints:
        return "present_unchecked"
    if any("arxiv" in error.lower() for error in evidence.errors):
        return "lookup_failed"
    return "absent"
