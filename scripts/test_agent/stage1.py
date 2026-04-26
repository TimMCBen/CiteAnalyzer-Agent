from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.analyzer import nodes
from apps.analyzer.nodes import initialize_state, parse_user_query, resolve_target_paper_node
from packages.shared.errors import InvalidAnalysisRequestError
from packages.shared.models import TargetPaper
from packages.shared.models import UserQuery


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


def parse_query(raw_query: str):
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
    for case in CASES:
        assert_case(case)
        print(f"[PASS] stage1::{case['name']}")

    assert_invalid_case(INVALID_CASE)
    print(f"[PASS] stage1::{INVALID_CASE['name']}")
    print("stage1 validation passed")


if __name__ == "__main__":
    main()
