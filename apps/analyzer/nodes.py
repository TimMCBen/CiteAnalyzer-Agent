"""Analyzer graph nodes that parse input, run stages, and attach results to state."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional

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

from packages.author_intel import attach_author_intel_result_to_state, analyze_author_intel_with_live_clients
from apps.analyzer.config import build_llm, invoke_llm_with_retry
from apps.analyzer.resolve import resolve_target_paper_metadata
from packages.citation_sources.service import attach_fetch_result_to_state, fetch_citation_candidates_with_live_clients
from packages.reporting import attach_report_artifact_to_state, build_report_artifact
from packages.sentiment.models import FullTextDocument
from packages.sentiment.models import SentimentSummary
from packages.shared.errors import InvalidAnalysisRequestError
from packages.shared.models import AnalysisState, AuthorSummary, ParsedUserIntent, TargetPaper, UserQuery
from packages.shared.runtime_logging import get_runtime_logger, get_runtime_options

DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
ARXIV_PATTERN = re.compile(r"(?:arxiv\.org/(?:abs|pdf)/)?(?P<identifier>\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?", re.IGNORECASE)
OPENALEX_PATTERN = re.compile(r"openalex:(?P<identifier>[A-Za-z0-9]+)", re.IGNORECASE)


class IntentExtractionModel(BaseModel):
    """Validate structured intent extraction data returned by the analyzer LLM."""
    request_type: str = Field(description="citation_analysis or unsupported")
    paper_query: Optional[str] = Field(default=None, description="The target paper clue from the user request")
    paper_query_type: str = Field(description="doi, paper_id, arxiv, title, or unknown")
    analysis_goal: Optional[str] = Field(default=None, description="What the user wants to know about the paper")
    constraints: Dict[str, str] = Field(default_factory=dict, description="Optional constraints like time range or output focus")
    reason: Optional[str] = Field(default=None, description="Reason when the request is unsupported or uncertain")


def fetch_fulltext_document(*args, **kwargs):
    """Lazy-load the full-text fetcher used by Stage 5 nodes."""
    from packages.sentiment.fulltext import fetch_fulltext_document as impl

    return impl(*args, **kwargs)


def analyze_citation_sentiments(*args, **kwargs):
    """Lazy-load the sentiment analyzer used by Stage 6 nodes."""
    from packages.sentiment.service import analyze_citation_sentiments as impl

    return impl(*args, **kwargs)


def attach_sentiment_result_to_state(*args, **kwargs):
    """Lazy-load the state adapter for sentiment outputs."""
    from packages.sentiment.service import attach_sentiment_result_to_state as impl

    return impl(*args, **kwargs)


def initialize_state(user_query: UserQuery) -> AnalysisState:
    """Create the initial analyzer state for a raw user query."""
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
    """Classify the user request and extract the target-paper clue."""
    get_runtime_logger().stage_start("stage1", "理解用户输入")
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
    get_runtime_logger().stage_done(
        "stage1",
        "已识别目标论文",
        type=target_paper.paper_query_type,
        query=target_paper.paper_query,
    )
    return state


def fetch_citation_candidates_node(state: AnalysisState) -> AnalysisState:
    """Fetch and attach citing-paper candidates for the resolved target."""
    get_runtime_logger().stage_start("stage2", "抓取施引文献")
    target_paper = state.get("target_paper")
    if not isinstance(target_paper, TargetPaper):
        raise RuntimeError("target_paper is missing from analysis state")
    if target_paper.resolve_status != "resolved":
        raise RuntimeError("target_paper must be resolved before fetching citation candidates")

    max_results = get_runtime_options().max_citations or 20
    result = fetch_citation_candidates_with_live_clients(target_paper=target_paper, max_results=max_results)
    if not result.citing_papers:
        get_runtime_logger().skip(
            "stage2",
            "Semantic Scholar 当前返回 0 篇施引文献，下游作者画像、全文和情感分析将跳过",
            reason="no_citing_papers",
        )
    else:
        get_runtime_logger().stage_done(
            "stage2",
            "施引文献抓取完成",
            semantic=result.fetch_summary.semantic_scholar_candidates,
            crossref_enriched=result.fetch_summary.crossref_candidates,
            deduped=result.fetch_summary.deduped_candidates,
        )
    return attach_fetch_result_to_state(state, result)


def resolve_target_paper_node(state: AnalysisState) -> AnalysisState:
    """Resolve target-paper metadata before citation collection."""
    get_runtime_logger().stage_start("stage1", "解析目标论文元数据")
    target_paper = state.get("target_paper")
    if not isinstance(target_paper, TargetPaper):
        raise RuntimeError("target_paper is missing from analysis state")

    resolved = resolve_target_paper_metadata(target_paper)
    state["target_paper"] = resolved
    state["status"] = "target_paper_resolved" if resolved.resolve_status == "resolved" else "target_paper_unresolved"
    if resolved.resolve_status != "resolved":
        get_runtime_logger().warn(
            "resolver",
            "目标论文元数据未能完全解析",
            query=resolved.paper_query,
            resolve_status=resolved.resolve_status,
        )
        state.setdefault("errors", [])
        state["errors"].append(
            f"target_paper_{resolved.paper_query_type}_resolution_failed"
        )
    else:
        get_runtime_logger().stage_done(
            "stage1",
            "目标论文元数据解析完成",
            title=resolved.title,
            doi=resolved.doi,
            canonical_id=resolved.canonical_id,
        )
    return state


def analyze_author_intel_node(state: AnalysisState) -> AnalysisState:
    """Build author profiles and scholar labels for citing papers."""
    get_runtime_logger().stage_start("stage4", "查询施引作者画像")
    citing_papers = state.get("citing_papers")
    if not isinstance(citing_papers, list):
        raise RuntimeError("citing_papers are required before stage4 author-intel analysis")
    if not citing_papers:
        state["author_profiles"] = []
        state["scholar_labels"] = []
        state["author_summary"] = AuthorSummary()
        state["status"] = "author_intel_skipped_no_citations"
        get_runtime_logger().skip("stage4", "没有施引文献，跳过作者画像", reason="no_citing_papers")
        return state

    result = analyze_author_intel_with_live_clients(citing_papers)
    get_runtime_logger().stage_done(
        "stage4",
        "作者画像完成",
        authors=len(result.author_profiles),
        matched=result.author_summary.matched_profiles,
        heavyweight=result.author_summary.heavyweight_candidates,
        high_impact=result.author_summary.high_impact_candidates,
    )
    return attach_author_intel_result_to_state(state, result)


def fetch_fulltext_documents_node(state: AnalysisState) -> AnalysisState:
    """Fetch available full-text artifacts for each citing paper."""
    get_runtime_logger().stage_start("stage5", "获取施引论文全文")
    citing_papers = state.get("citing_papers")
    if not isinstance(citing_papers, list):
        raise RuntimeError("citing_papers are required before stage5 fulltext fetch")
    if not citing_papers:
        state["fulltext_documents"] = {}
        state["status"] = "fulltext_skipped_no_citations"
        get_runtime_logger().skip("stage5", "没有施引文献，跳过全文获取", reason="no_citing_papers")
        return state

    save_dir = Path("downloaded-papers") / "stage5"
    fulltext_documents: dict[str, FullTextDocument] = {}
    errors: list[str] = []

    for citing_paper in citing_papers:
        try:
            document = fetch_fulltext_document(
                citing_paper,
                search_arxiv_fallback=True,
                save_dir=save_dir,
            )
        except Exception as exc:  # pragma: no cover - network/runtime path
            errors.append(f"stage5:{citing_paper.canonical_id}:{exc}")
            get_runtime_logger().warn(
                "fulltext.fetch",
                "单篇全文获取失败，后续会降级处理",
                citing_paper_id=citing_paper.canonical_id,
                error_type=exc.__class__.__name__,
                impact="single_paper",
            )
            continue
        if document is not None:
            fulltext_documents[citing_paper.canonical_id] = document
            get_runtime_logger().detail(
                "fulltext.fetch",
                "全文获取成功",
                citing_paper_id=citing_paper.canonical_id,
                source_type=document.source_type,
                path=document.local_path or document.raw_path,
            )

    state["fulltext_documents"] = fulltext_documents  # type: ignore[assignment]
    if errors:
        state.setdefault("errors", [])
        state["errors"].extend(errors)
    state["status"] = "fulltext_documents_fetched"
    get_runtime_logger().stage_done(
        "stage5",
        "全文获取完成",
        available=len(fulltext_documents),
        missing=len(citing_papers) - len(fulltext_documents),
    )
    return state


def analyze_citation_sentiments_node(state: AnalysisState) -> AnalysisState:
    """Extract citation contexts and attach sentiment classifications."""
    get_runtime_logger().stage_start("stage6", "提取引用上下文并判断情感")
    target_paper = state.get("target_paper")
    citing_papers = state.get("citing_papers")
    fulltext_documents = state.get("fulltext_documents")

    if not isinstance(target_paper, TargetPaper):
        raise RuntimeError("target_paper is required before stage6 sentiment analysis")
    if not isinstance(citing_papers, list):
        raise RuntimeError("citing_papers are required before stage6 sentiment analysis")
    if not citing_papers:
        state["citation_contexts"] = []
        state["sentiment_summary"] = SentimentSummary(total_candidates=0)
        state["status"] = "citation_sentiments_skipped_no_citations"
        get_runtime_logger().skip("stage6", "没有施引文献，跳过引用上下文和情感分析", reason="no_citing_papers")
        return state

    result = analyze_citation_sentiments(
        target_paper=target_paper,
        citing_papers=citing_papers,
        fulltext_documents=fulltext_documents if isinstance(fulltext_documents, dict) else None,
        allow_network=True,
        search_arxiv_fallback=True,
    )
    get_runtime_logger().stage_done(
        "stage6",
        "情感分析完成",
        positive=result.summary.label_counts.get("positive", 0),
        neutral=result.summary.label_counts.get("neutral", 0),
        critical=result.summary.label_counts.get("critical", 0),
        unknown=result.summary.label_counts.get("unknown", 0),
    )
    return attach_sentiment_result_to_state(state, result)


def generate_report_node(state: AnalysisState) -> AnalysisState:
    """Generate and attach the final HTML, JSON, and PDF report artifacts."""
    get_runtime_logger().stage_start("stage7", "生成 HTML / JSON / PDF 报告")
    target_paper = state.get("target_paper")
    citing_papers = state.get("citing_papers")
    author_profiles = state.get("author_profiles")
    scholar_labels = state.get("scholar_labels")
    author_summary = state.get("author_summary")
    citation_contexts = state.get("citation_contexts")
    sentiment_summary = state.get("sentiment_summary")

    if not isinstance(target_paper, TargetPaper):
        raise RuntimeError("target_paper is required before stage7 report generation")
    if not isinstance(citing_papers, list):
        raise RuntimeError("citing_papers are required before stage7 report generation")
    if not isinstance(author_profiles, list) or not isinstance(scholar_labels, list):
        raise RuntimeError("author_intel outputs are required before stage7 report generation")
    if author_summary is None or not isinstance(citation_contexts, list) or sentiment_summary is None:
        raise RuntimeError("sentiment outputs are required before stage7 report generation")

    artifact = build_report_artifact(
        target_paper=target_paper,
        citing_papers=citing_papers,
        author_profiles=author_profiles,
        scholar_labels=scholar_labels,
        author_summary=author_summary,
        citation_contexts=citation_contexts,
        sentiment_summary=sentiment_summary,
        fetch_summary=state.get("fetch_summary"),
        source_trace=state.get("source_trace") if isinstance(state.get("source_trace"), list) else None,
        state_errors=state.get("errors") if isinstance(state.get("errors"), list) else None,
    )
    get_runtime_logger().stage_done(
        "stage7",
        "报告生成完成",
        html=artifact.export_paths.get("html"),
        json=artifact.export_paths.get("json"),
        pdf=artifact.export_paths.get("pdf"),
    )
    return attach_report_artifact_to_state(state, artifact)


def parse_with_llm(raw_query: str) -> ParsedUserIntent:
    """Use the configured LLM to extract structured intent from a query."""
    llm = build_llm()
    structured_llm = llm.with_structured_output(IntentExtractionModel, method="function_calling")

    prompt = (
        "你是论文被引分析智能体的输入解析器。"
        "请从用户输入中提取目标论文线索、分析目标和约束。"
        "如果用户不是在请求分析某篇论文的被引情况，则将 request_type 设为 unsupported。"
        "如果用户在请求被引分析，但论文线索不足以唯一定位，请保留 request_type 为 citation_analysis，"
        "并将 paper_query_type 设为 unknown。"
    )

    result = invoke_llm_with_retry(
        structured_llm,
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": raw_query},
        ],
        "阶段1输入解析",
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
    """Extract target-paper intent with deterministic fallback patterns."""
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
    """Return whether deterministic parsing should override weak LLM intent."""
    if parsed.request_type != "citation_analysis":
        return False
    if parsed.paper_query_type in {"doi", "paper_id", "arxiv"}:
        return False
    return bool(DOI_PATTERN.search(raw_query) or ARXIV_PATTERN.search(raw_query) or OPENALEX_PATTERN.search(raw_query))


def extract_title_clue(raw_query: str) -> Optional[str]:
    """Extract a quoted title clue from a natural-language query."""
    matches = re.findall(r"[\"“”](.*?)[\"“”]", raw_query)
    if matches:
        return matches[0].strip()
    return None


def clean_title_like_query(raw_query: str) -> str:
    """Normalize title-like user queries before fallback parsing."""
    cleaned = raw_query
    for fragment in ["帮我分析一下", "请查看", "分析一下", "我想知道", "这篇论文", "的被引情况", "有哪些施引文献", "的引用情感", "的主要引用者和情感倾向"]:
        cleaned = cleaned.replace(fragment, "")
    return cleaned.strip(" ，。！？:：")


def looks_like_citation_analysis(raw_query: str) -> bool:
    """Return whether a query appears to request paper citation analysis."""
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
