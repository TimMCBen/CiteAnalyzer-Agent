"""Validate Stage 1 user-query parsing and target-paper resolution."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.analyzer import nodes
from apps.analyzer import resolve as resolver
from apps.analyzer.nodes import initialize_state, parse_user_query, resolve_target_paper_node
from apps.analyzer import config as analyzer_config
from packages.shared.errors import InvalidAnalysisRequestError
from packages.shared.models import TargetPaper
from packages.shared.models import UserQuery
from packages.shared.web_search import WebSearchResult
from scripts.test_agent.stage_logging import StageLogger


CASES = [
    {
        "name": "title_clue_request",
        "query": "帮我分析一下 Attention Is All You Need 的被引情况",
        "expected_request_type": "citation_analysis",
        "expected_query_type": "title",
        "expected_paper_query": "Attention Is All You Need",
        "expected_resolve_status": "resolved",
        "expected_title": "Attention Is All You Need",
    },
    {
        "name": "doi_request",
        "query": "请查看 DOI 为 10.1145/3368089.3409740 的论文有哪些施引文献",
        "expected_request_type": "citation_analysis",
        "expected_query_type": "doi",
        "expected_paper_query": "10.1145/3368089.3409740",
        "expected_resolve_status": "resolved",
        "expected_title": "Towards automated verification of smart contract fairness",
    },
    {
        "name": "arxiv_request",
        "query": "分析一下这篇 arXiv 论文 https://arxiv.org/abs/1706.03762 的引用情感",
        "expected_request_type": "citation_analysis",
        "expected_query_type": "arxiv",
        "expected_paper_query": "1706.03762",
        "expected_resolve_status": "resolved",
        "expected_title": "Attention Is All You Need",
    },
    {
        "name": "arxiv_pdf_request",
        "query": "分析一下这篇 arXiv PDF https://arxiv.org/pdf/2507.19457 的引用情感",
        "expected_request_type": "citation_analysis",
        "expected_query_type": "arxiv",
        "expected_paper_query": "2507.19457",
        "expected_resolve_status": "resolved",
        "expected_title": "Current PDF Smoke Target",
    },
    {
        "name": "openalex_request",
        "query": "我想知道 openalex:W2741809807 这篇论文的主要引用者和情感倾向",
        "expected_request_type": "citation_analysis",
        "expected_query_type": "paper_id",
        "expected_paper_query": "W2741809807",
        "expected_resolve_status": "unresolved",
        "expected_title": None,
    },
]

INVALID_CASE = {
    "name": "unsupported_request",
    "query": "帮我总结一下 LangGraph 是什么",
}


def assert_case(case: dict[str, str]) -> None:
    state = parse_query(case["query"])
    target_paper = state["target_paper"]

    assert state["request_type"] == case["expected_request_type"], (
        f"{case['name']}: expected request_type={case['expected_request_type']}, "
        f"got {state['request_type']}"
    )
    assert target_paper.paper_query_type == case["expected_query_type"], (
        f"{case['name']}: expected paper_query_type={case['expected_query_type']}, "
        f"got {target_paper.paper_query_type}"
    )
    assert target_paper.paper_query == case["expected_paper_query"], (
        f"{case['name']}: expected paper_query={case['expected_paper_query']!r}, "
        f"got {target_paper.paper_query!r}"
    )
    assert target_paper.resolve_status == case["expected_resolve_status"], (
        f"{case['name']}: expected resolve_status={case['expected_resolve_status']}, "
        f"got {target_paper.resolve_status}"
    )
    assert target_paper.title == case["expected_title"], (
        f"{case['name']}: expected title={case['expected_title']!r}, got {target_paper.title!r}"
    )


def assert_invalid_case(case: dict[str, str]) -> None:
    try:
        parse_query(case["query"])
    except InvalidAnalysisRequestError:
        return

    raise AssertionError(f"{case['name']}: expected InvalidAnalysisRequestError")


def assert_web_search_title_fallback() -> None:
    """Assert Stage 1 can use web-search results plus LLM verification for arXiv titles."""
    original_from_env = resolver.GenericWebSearchClient.from_env
    original_build_llm = analyzer_config.build_llm
    original_invoke = analyzer_config.invoke_llm_with_retry
    original_load_env = analyzer_config.load_local_env

    class FakeSearchClient:
        """Return a deterministic web-search row for the title fallback contract."""
        def search(self, query: str, *, max_results: int = 5):
            """Assert the arXiv ID is queried and return one matching result."""
            assert "2507.19457" in query
            return [
                WebSearchResult(
                    title="GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning",
                    url="https://huggingface.co/papers/2507.19457",
                    snippet="arXiv:2507.19457 GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning",
                    source="fake",
                )
            ]

    class FakeLLM:
        """Expose the structured-output method expected from the analyzer LLM."""
        def with_structured_output(self, *_args, **_kwargs):
            """Return self so the fake retry helper can supply the decision."""
            return self

    class Decision:
        """Structured title-selection result returned by the fake LLM."""
        title = "GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning"
        confidence = "high"
        source_url = "https://huggingface.co/papers/2507.19457"
        evidence_zh = "搜索结果标题和 arXiv ID 同时匹配。"

    resolver.GenericWebSearchClient.from_env = classmethod(lambda cls: FakeSearchClient())  # type: ignore[method-assign]
    analyzer_config.build_llm = lambda: FakeLLM()  # type: ignore[assignment]
    analyzer_config.invoke_llm_with_retry = lambda *_args, **_kwargs: Decision()  # type: ignore[assignment]
    analyzer_config.load_local_env = lambda **_kwargs: None  # type: ignore[assignment]
    try:
        resolved = resolver._resolve_arxiv_from_web_search(  # type: ignore[attr-defined]
            TargetPaper(paper_query="2507.19457", paper_query_type="arxiv"),
            "2507.19457",
            reason="test",
        )
    finally:
        resolver.GenericWebSearchClient.from_env = original_from_env  # type: ignore[method-assign]
        analyzer_config.build_llm = original_build_llm  # type: ignore[assignment]
        analyzer_config.invoke_llm_with_retry = original_invoke  # type: ignore[assignment]
        analyzer_config.load_local_env = original_load_env  # type: ignore[assignment]

    assert resolved is not None
    assert resolved.title == "GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning"
    assert resolved.source_ids["web_search"] == "https://huggingface.co/papers/2507.19457"


def parse_query(raw_query: str):
    """Parse a query with deterministic LLM and resolver fakes."""
    original_parse_with_llm = nodes.parse_with_llm
    original_resolve_target_paper_metadata = nodes.resolve_target_paper_metadata

    def force_fallback(_: str):
        raise RuntimeError("force fallback parser for deterministic stage1 validation")

    def fake_resolver(target_paper: TargetPaper) -> TargetPaper:
        if target_paper.paper_query_type == "doi" and target_paper.doi == "10.1145/3368089.3409740":
            return TargetPaper(
                canonical_id="10.1145/3368089.3409740",
                paper_query=target_paper.paper_query,
                paper_query_type=target_paper.paper_query_type,
                title="Towards automated verification of smart contract fairness",
                doi="10.1145/3368089.3409740",
                source_ids={"doi": "10.1145/3368089.3409740", "crossref": "10.1145/3368089.3409740"},
                resolve_status="resolved",
            )
        if target_paper.paper_query_type == "arxiv" and target_paper.paper_query == "1706.03762":
            return TargetPaper(
                canonical_id="1706.03762",
                paper_query=target_paper.paper_query,
                paper_query_type=target_paper.paper_query_type,
                title="Attention Is All You Need",
                doi="10.48550/arXiv.1706.03762",
                source_ids={"arxiv": "1706.03762", "doi": "10.48550/arXiv.1706.03762"},
                resolve_status="resolved",
            )
        if target_paper.paper_query_type == "arxiv" and target_paper.paper_query == "2507.19457":
            return TargetPaper(
                canonical_id="2507.19457",
                paper_query=target_paper.paper_query,
                paper_query_type=target_paper.paper_query_type,
                title="Current PDF Smoke Target",
                doi=None,
                source_ids={"arxiv": "2507.19457"},
                resolve_status="resolved",
            )
        if target_paper.paper_query_type == "title" and target_paper.paper_query == "Attention Is All You Need":
            return TargetPaper(
                canonical_id="1706.03762",
                paper_query=target_paper.paper_query,
                paper_query_type=target_paper.paper_query_type,
                title="Attention Is All You Need",
                doi="10.48550/arXiv.1706.03762",
                source_ids={"arxiv": "1706.03762", "doi": "10.48550/arXiv.1706.03762"},
                resolve_status="resolved",
            )
        if target_paper.paper_query_type == "paper_id":
            return TargetPaper(
                canonical_id=None,
                paper_query=target_paper.paper_query,
                paper_query_type=target_paper.paper_query_type,
                title=None,
                doi=None,
                source_ids={},
                resolve_status="unresolved",
            )
        return target_paper

    nodes.parse_with_llm = force_fallback
    nodes.resolve_target_paper_metadata = fake_resolver
    try:
        state = initialize_state(UserQuery(raw_text=raw_query))
        state = parse_user_query(state)
        return resolve_target_paper_node(state)
    finally:
        nodes.parse_with_llm = original_parse_with_llm
        nodes.resolve_target_paper_metadata = original_resolve_target_paper_metadata


def main() -> None:
    """Run Stage 1 parsing and unsupported-request assertions."""
    logger = StageLogger("stage1")
    logger.start()
    for case in CASES:
        state = parse_query(case["query"])
        target_paper = state["target_paper"]
        assert_case(case)
        logger.pass_case(
            case["name"],
            detail=(
                f"expected_type={case['expected_query_type']} "
                f"parsed_type={target_paper.paper_query_type} resolve_status={target_paper.resolve_status}"
            ),
        )

    assert_invalid_case(INVALID_CASE)
    logger.pass_case("unsupported_request", detail="raised=InvalidAnalysisRequestError")
    assert_web_search_title_fallback()
    logger.pass_case("web_search_title_fallback", detail="provider=fake llm=structured")
    logger.done("stage1 validation passed")


if __name__ == "__main__":
    main()
