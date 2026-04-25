from __future__ import annotations

import re
from typing import Dict, Optional

from pydantic import BaseModel, Field

from apps.analyzer.config import build_llm
from packages.shared.errors import InvalidAnalysisRequestError
from packages.shared.models import AnalysisState, ParsedUserIntent, TargetPaper, UserQuery

DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
ARXIV_PATTERN = re.compile(r"(?:arxiv\.org/(?:abs|pdf)/)?(?P<identifier>\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?", re.IGNORECASE)
OPENALEX_PATTERN = re.compile(r"openalex:(?P<identifier>[A-Za-z0-9]+)", re.IGNORECASE)


class IntentExtractionModel(BaseModel):
    request_type: str = Field(description="citation_analysis or unsupported")
    paper_query: Optional[str] = Field(default=None, description="The target paper clue from the user request")
    paper_query_type: str = Field(description="doi, paper_id, arxiv, title, or unknown")
    analysis_goal: Optional[str] = Field(default=None, description="What the user wants to know about the paper")
    constraints: Dict[str, str] = Field(default_factory=dict, description="Optional constraints like time range or output focus")
    reason: Optional[str] = Field(default=None, description="Reason when the request is unsupported or uncertain")


def initialize_state(user_query: UserQuery) -> AnalysisState:
    return AnalysisState(
        raw_query=user_query.raw_text,
        request_type="pending",
        analysis_goal="pending",
        constraints={},
        target_paper=TargetPaper(),
        errors=[],
        status="initialized",
    )


def parse_user_query(state: AnalysisState) -> AnalysisState:
    try:
        parsed = parse_with_llm(state["raw_query"])
    except Exception:
        parsed = parse_with_fallback_rules(state["raw_query"])

    if parsed.request_type != "citation_analysis" and looks_like_citation_analysis(state["raw_query"]):
        parsed = parse_with_fallback_rules(state["raw_query"])
    elif should_retry_fallback_for_concrete_id(parsed, state["raw_query"]):
        fallback_parsed = parse_with_fallback_rules(state["raw_query"])
        if fallback_parsed.paper_query_type in {"doi", "paper_id", "arxiv"}:
            parsed = ParsedUserIntent(
                request_type=fallback_parsed.request_type,
                paper_query=fallback_parsed.paper_query,
                paper_query_type=fallback_parsed.paper_query_type,
                analysis_goal=parsed.analysis_goal or fallback_parsed.analysis_goal,
                constraints=parsed.constraints,
                reason=parsed.reason or fallback_parsed.reason,
            )

    if parsed.request_type != "citation_analysis":
        raise InvalidAnalysisRequestError(parsed.reason or "The request is not a paper citation-analysis request.")

    target_paper = TargetPaper(
        canonical_id=None,
        paper_query=parsed.paper_query,
        paper_query_type=parsed.paper_query_type,
        title=parsed.paper_query if parsed.paper_query_type == "title" else None,
        doi=parsed.paper_query.lower() if parsed.paper_query_type == "doi" and parsed.paper_query else None,
        source_ids={parsed.paper_query_type: parsed.paper_query} if parsed.paper_query and parsed.paper_query_type in {"paper_id", "arxiv"} else {},
        resolve_status="uncertain" if parsed.paper_query_type in {"title", "unknown"} else "resolved",
    )

    state["request_type"] = parsed.request_type
    state["analysis_goal"] = parsed.analysis_goal or "citation_analysis"
    state["constraints"] = parsed.constraints
    state["target_paper"] = target_paper
    state["status"] = "parsed"
    return state


def parse_with_llm(raw_query: str) -> ParsedUserIntent:
    llm = build_llm()
    structured_llm = llm.with_structured_output(IntentExtractionModel, method="function_calling")

    prompt = (
        "你是论文被引分析智能体的输入解析器。"
        "请从用户输入中提取目标论文线索、分析目标和约束。"
        "如果用户不是在请求分析某篇论文的被引情况，则将 request_type 设为 unsupported。"
        "如果用户在请求被引分析，但论文线索不足以唯一定位，请保留 request_type 为 citation_analysis，"
        "并将 paper_query_type 设为 unknown。"
    )

    result = structured_llm.invoke(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": raw_query},
        ]
    )

    return ParsedUserIntent(
        request_type="citation_analysis" if result.request_type == "citation_analysis" else "unsupported",
        paper_query=result.paper_query,
        paper_query_type=result.paper_query_type if result.paper_query_type in {"doi", "paper_id", "arxiv", "title", "unknown"} else "unknown",
        analysis_goal=result.analysis_goal,
        constraints=result.constraints,
        reason=result.reason,
    )


def parse_with_fallback_rules(raw_query: str) -> ParsedUserIntent:
    lowered = raw_query.lower()

    if not looks_like_citation_analysis(raw_query):
        return ParsedUserIntent(
            request_type="unsupported",
            reason="The request does not appear to ask for paper citation analysis.",
        )

    doi_match = DOI_PATTERN.search(raw_query)
    if doi_match:
        return ParsedUserIntent(
            request_type="citation_analysis",
            paper_query=doi_match.group(0).lower(),
            paper_query_type="doi",
            analysis_goal="citation_analysis",
        )

    openalex_match = OPENALEX_PATTERN.search(raw_query)
    if openalex_match:
        return ParsedUserIntent(
            request_type="citation_analysis",
            paper_query=openalex_match.group("identifier"),
            paper_query_type="paper_id",
            analysis_goal="citation_analysis",
        )

    arxiv_match = ARXIV_PATTERN.search(raw_query)
    if arxiv_match:
        return ParsedUserIntent(
            request_type="citation_analysis",
            paper_query=arxiv_match.group("identifier"),
            paper_query_type="arxiv",
            analysis_goal="citation_analysis",
        )

    quoted_title = extract_title_clue(raw_query)
    if quoted_title:
        return ParsedUserIntent(
            request_type="citation_analysis",
            paper_query=quoted_title,
            paper_query_type="title",
            analysis_goal="citation_analysis",
            reason="Title clue extracted from natural-language request.",
        )

    cleaned = clean_title_like_query(raw_query)
    return ParsedUserIntent(
        request_type="citation_analysis",
        paper_query=cleaned if cleaned else None,
        paper_query_type="title" if cleaned else "unknown",
        analysis_goal="citation_analysis",
        reason="Fallback parser could not confidently identify a unique paper handle.",
    )


def should_retry_fallback_for_concrete_id(parsed: ParsedUserIntent, raw_query: str) -> bool:
    if parsed.request_type != "citation_analysis":
        return False
    if parsed.paper_query_type in {"doi", "paper_id", "arxiv"}:
        return False
    return bool(DOI_PATTERN.search(raw_query) or ARXIV_PATTERN.search(raw_query) or OPENALEX_PATTERN.search(raw_query))


def extract_title_clue(raw_query: str) -> Optional[str]:
    matches = re.findall(r"[\"“”](.*?)[\"“”]", raw_query)
    if matches:
        return matches[0].strip()
    return None


def clean_title_like_query(raw_query: str) -> str:
    cleaned = raw_query
    for fragment in ["帮我分析一下", "请查看", "分析一下", "我想知道", "这篇论文", "的被引情况", "有哪些施引文献", "的引用情感", "的主要引用者和情感倾向"]:
        cleaned = cleaned.replace(fragment, "")
    return cleaned.strip(" ，。！？:：")


def looks_like_citation_analysis(raw_query: str) -> bool:
    lowered = raw_query.lower()
    if DOI_PATTERN.search(raw_query) or ARXIV_PATTERN.search(raw_query) or OPENALEX_PATTERN.search(raw_query):
        return True

    return any(
        keyword in lowered
        for keyword in [
            "被引",
            "引用",
            "施引",
            "引用者",
            "引文",
            "citation",
            "cited",
        ]
    ) or (
        any(keyword in lowered for keyword in ["分析", "analyze"])
        and any(keyword in lowered for keyword in ["论文", "文章", "paper"])
    )
