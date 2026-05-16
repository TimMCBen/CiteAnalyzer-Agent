from __future__ import annotations

from collections.abc import Callable

from apps.analyzer.graph import build_stage1_graph, build_stage2_graph, build_stage6_graph, build_stage7_graph
from apps.analyzer.nodes import initialize_state
from packages.shared.models import AnalysisState, UserQuery
from packages.shared.runtime_logging import AnalysisRuntimeOptions, RuntimeLogger, RuntimeLogMode, runtime_context


def run_stage1_analysis(
    raw_text: str,
    *,
    runtime_log_mode: RuntimeLogMode | None = None,
    max_citations: int | None = None,
) -> AnalysisState:
    return _invoke_graph(
        raw_text,
        build_stage1_graph,
        runtime_log_mode=runtime_log_mode,
        max_citations=max_citations,
    )


def run_stage2_analysis(
    raw_text: str,
    *,
    runtime_log_mode: RuntimeLogMode | None = None,
    max_citations: int | None = None,
) -> AnalysisState:
    return _invoke_graph(
        raw_text,
        build_stage2_graph,
        runtime_log_mode=runtime_log_mode,
        max_citations=max_citations,
    )


def run_stage6_analysis(
    raw_text: str,
    *,
    runtime_log_mode: RuntimeLogMode | None = None,
    max_citations: int | None = None,
) -> AnalysisState:
    return _invoke_graph(
        raw_text,
        build_stage6_graph,
        runtime_log_mode=runtime_log_mode,
        max_citations=max_citations,
    )


def run_stage7_analysis(
    raw_text: str,
    *,
    runtime_log_mode: RuntimeLogMode | None = None,
    max_citations: int | None = None,
) -> AnalysisState:
    return _invoke_graph(
        raw_text,
        build_stage7_graph,
        runtime_log_mode=runtime_log_mode,
        max_citations=max_citations,
    )


def run_analysis(
    raw_text: str,
    *,
    runtime_log_mode: RuntimeLogMode | None = None,
    max_citations: int | None = None,
) -> AnalysisState:
    return run_stage7_analysis(
        raw_text,
        runtime_log_mode=runtime_log_mode,
        max_citations=max_citations,
    )


def _invoke_graph(
    raw_text: str,
    graph_builder: Callable[[], object],
    *,
    runtime_log_mode: RuntimeLogMode | None,
    max_citations: int | None,
) -> AnalysisState:
    query = UserQuery(raw_text=raw_text)
    state = initialize_state(query)
    app = graph_builder()
    logger = RuntimeLogger(component="analyzer", mode=runtime_log_mode)
    options = AnalysisRuntimeOptions(max_citations=max_citations)
    with runtime_context(logger=logger, options=options):
        try:
            final_state = app.invoke(state)
        except Exception as exc:
            logger.fail("analyzer", "分析流程失败，保留原始异常继续抛出", error_type=exc.__class__.__name__)
            logger.summary(status="failed", reason=exc)
            raise
        logger.summary(**_build_summary_fields(final_state))
        return final_state


def _build_summary_fields(state: AnalysisState) -> dict[str, object]:
    target = state.get("target_paper")
    target_label = "unknown"
    if target is not None:
        target_label = (
            getattr(target, "canonical_id", None)
            or getattr(target, "doi", None)
            or getattr(target, "paper_query", None)
            or "unknown"
        )

    citing_papers = state.get("citing_papers") if isinstance(state.get("citing_papers"), list) else []
    author_profiles = state.get("author_profiles") if isinstance(state.get("author_profiles"), list) else []
    fulltext_documents = state.get("fulltext_documents") if isinstance(state.get("fulltext_documents"), dict) else {}
    citation_contexts = state.get("citation_contexts") if isinstance(state.get("citation_contexts"), list) else []
    sentiment_summary = state.get("sentiment_summary")
    report_artifact = state.get("report_artifact")

    sentiment = "未执行"
    if sentiment_summary is not None:
        label_counts = getattr(sentiment_summary, "label_counts", {})
        sentiment = (
            f"中性 {label_counts.get('neutral', 0)} / "
            f"正向 {label_counts.get('positive', 0)} / "
            f"批评 {label_counts.get('critical', 0)} / "
            f"未知 {label_counts.get('unknown', 0)}"
        )

    report_path = ""
    if report_artifact is not None:
        report_path = getattr(report_artifact, "export_paths", {}).get("html", "")

    grobid_hits = sum(
        1
        for context in citation_contexts
        if "matched_by_grobid" in str(getattr(context, "evidence_note", ""))
    )

    return {
        "target": target_label,
        "citing_papers": f"{len(citing_papers)} 篇",
        "author_profiles": f"{len(author_profiles)} 位作者",
        "fulltext": f"{len(fulltext_documents)}/{len(citing_papers)}",
        "grobid": f"{grobid_hits}/{len(citation_contexts)}",
        "sentiment": sentiment,
        "degradation": f"errors={len(state.get('errors', []))}",
        "report": report_path,
        "status": state.get("status", "unknown"),
    }
