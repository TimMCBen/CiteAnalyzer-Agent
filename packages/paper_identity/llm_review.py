from __future__ import annotations

try:
    from pydantic import BaseModel, Field
except ImportError:
    class BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    def Field(default=None, **kwargs):  # type: ignore
        if "default_factory" in kwargs:
            return kwargs["default_factory"]()
        return default

from packages.paper_identity.models import LLMIdentityReview, PaperIdentityDecision, PaperIdentityEvidence


class LLMIdentityReviewModel(BaseModel):
    paper_identity_decision: str = Field(description="same_paper, different_paper, or uncertain")
    paper_confidence: str = Field(description="high, medium, low, miss, or error")
    selected_source: str = Field(description="doi_candidate, arxiv_candidate, openalex_title_candidate, semantic_scholar_only, or none")
    doi_assessment: str = Field(description="verified, variant, mismatch, absent, or unverified")
    arxiv_assessment: str = Field(description="verified, variant, mismatch, absent, or unverified")
    openalex_work_assessment: str = Field(description="verified, variant, mismatch, absent, or unverified")
    author_resolution_decision: str = Field(description="use_work_authorships, use_name_search, skip, or manual_review")
    author_confidence: str = Field(description="high, medium, low, weak, or unknown")
    risk_flags: list[str] = Field(default_factory=list, description="Short machine-readable risk flags")
    needs_manual_review: bool = Field(description="Whether a human should review this case")
    reason_zh: str = Field(description="中文理由，必须引用输入证据，不要凭空猜测")


def review_identity_with_llm(evidence: PaperIdentityEvidence, decision: PaperIdentityDecision) -> LLMIdentityReview:
    from apps.analyzer.config import build_llm, invoke_llm_with_retry

    llm = build_llm()
    structured_llm = llm.with_structured_output(LLMIdentityReviewModel, method="function_calling")
    result = invoke_llm_with_retry(
        structured_llm,
        [
            {
                "role": "system",
                "content": (
                    "你是论文身份核验审查员。你只能基于用户给出的候选证据判断，不能联网，不能凭空补事实。"
                    "字段名和结构化取值不要翻译，reason_zh 必须使用中文。"
                    "硬约束：无候选证据不能判 high；网络失败不能当成不存在；标题明显不同且作者无重合不能判 high；"
                    "没有 work authorships 时作者消歧不能判 high。"
                ),
            },
            {
                "role": "user",
                "content": _build_review_prompt(evidence, decision),
            },
        ],
        operation="论文身份复核",
    )
    return LLMIdentityReview(
        paper_identity_decision=_safe_value(result.paper_identity_decision, {"same_paper", "different_paper", "uncertain"}, "uncertain"),
        paper_confidence=_safe_value(result.paper_confidence, {"high", "medium", "low", "miss", "error"}, "medium"),
        selected_source=str(result.selected_source or "none"),
        doi_assessment=str(result.doi_assessment or "unverified"),
        arxiv_assessment=str(result.arxiv_assessment or "unverified"),
        openalex_work_assessment=str(result.openalex_work_assessment or "unverified"),
        author_resolution_decision=str(result.author_resolution_decision or "manual_review"),
        author_confidence=str(result.author_confidence or "unknown"),
        risk_flags=[str(item) for item in list(result.risk_flags or []) if item],
        needs_manual_review=bool(result.needs_manual_review),
        reason_zh=str(result.reason_zh or "").strip(),
    )


def _build_review_prompt(evidence: PaperIdentityEvidence, decision: PaperIdentityDecision) -> str:
    selected = decision.selected_work
    return "\n".join(
        [
            "请判断 Semantic Scholar 施引论文与候选 work 是否为同一篇，并判断是否可用 work.authorships 做作者消歧。",
            f"S2 ID: {evidence.citing_paper_id}",
            f"S2 标题: {evidence.title}",
            f"S2 DOI: {evidence.doi}",
            f"S2 年份: {evidence.year}",
            f"S2 作者: {', '.join(evidence.authors)}",
            f"规则判定: {decision.to_log_dict()}",
            f"DOI 候选: {_work_line(evidence.doi_work)}",
            f"标题候选: {[_work_line(work) for work in evidence.title_work_candidates[:3]]}",
            f"arXiv 候选: {[_work_line(work) for work in evidence.arxiv_candidates[:3]]}",
            f"当前 selected_work: {_work_line(selected)}",
        ]
    )


def _work_line(work) -> str:
    if work is None:
        return "None"
    return (
        f"id={work.work_id}; title={work.title}; doi={work.doi}; year={work.year}; "
        f"type={work.work_type}; arxiv={work.arxiv_id}; authors={len(work.authors)}"
    )


def _safe_value(value: object, allowed: set[str], fallback: str) -> str:
    text = str(value or "").strip()
    return text if text in allowed else fallback
