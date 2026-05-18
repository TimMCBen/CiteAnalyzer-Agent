"""Run the LLM-only paper identity baseline over evaluation evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.analyzer.config import build_llm, invoke_llm_with_retry
from packages.citation_sources.models import CitingPaper
from packages.paper_identity.clients.arxiv import ArxivMetadataClient
from packages.paper_identity.clients.openalex_work import OpenAlexWorkClient
from packages.paper_identity.llm_review import LLMIdentityReviewModel
from packages.paper_identity.service import build_identity_evidence
from scripts.eval.paper_identity_run_pipeline import read_jsonl, to_citing_paper


def parse_args() -> argparse.Namespace:
    """Parse CLI options for the LLM baseline runner."""
    parser = argparse.ArgumentParser(description="Run pure GPT paper identity baseline over the same evidence packet.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=Path("reports/eval/llm_baseline_predictions.jsonl"))
    return parser.parse_args()


def main() -> None:
    """Write baseline identity predictions for every dataset row."""
    args = parse_args()
    papers = [to_citing_paper(row) for row in read_jsonl(args.dataset)]
    openalex = OpenAlexWorkClient()
    arxiv = ArxivMetadataClient()
    llm = build_llm().with_structured_output(LLMIdentityReviewModel, method="function_calling")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for paper in papers:
            before_openalex = openalex.http_attempt_count
            before_arxiv = arxiv.http_attempt_count
            evidence = build_identity_evidence(paper, openalex_client=openalex, arxiv_client=arxiv)
            result = invoke_llm_with_retry(
                llm,
                [
                    {
                        "role": "system",
                        "content": (
                            "你是论文身份核验 baseline。只能基于输入 evidence 判断，不能联网，不能使用程序规则结论。"
                            "无候选证据不能判 high；网络失败不能当成不存在；reason_zh 必须中文且引用证据。"
                        ),
                    },
                    {"role": "user", "content": json.dumps(_evidence_packet(paper, evidence), ensure_ascii=False)},
                ],
                operation="论文身份纯 GPT baseline",
            )
            row = {
                "s2_paper_id": paper.canonical_id,
                "paper_identity_decision": result.paper_identity_decision,
                "paper_match_confidence": result.paper_confidence,
                "selected_work_id": _selected_work_id(result.selected_source, evidence),
                "doi_status": _doi_status(result.doi_assessment),
                "needs_manual_review": bool(result.needs_manual_review),
                "llm_call_count": 1,
                "api_call_count": (openalex.http_attempt_count - before_openalex) + (arxiv.http_attempt_count - before_arxiv),
                "reason_zh": result.reason_zh,
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(papers)} baseline predictions to {args.out}")


def _evidence_packet(paper: CitingPaper, evidence) -> dict[str, Any]:
    """Build the evidence packet passed to the baseline LLM."""
    return {
        "s2_paper_id": paper.canonical_id,
        "s2_title": paper.title,
        "s2_doi": paper.doi,
        "s2_year": paper.year,
        "s2_authors": paper.authors,
        "arxiv_id_hints": evidence.arxiv_id_hints,
        "doi_work": _work_packet(evidence.doi_work),
        "title_work_candidates": [_work_packet(work) for work in evidence.title_work_candidates[:3]],
        "arxiv_candidates": [_work_packet(work) for work in evidence.arxiv_candidates[:3]],
        "errors": evidence.errors,
    }


def _work_packet(work) -> dict[str, Any] | None:
    """Serialize one candidate work for LLM baseline review."""
    if work is None:
        return None
    return {
        "source": work.source,
        "work_id": work.work_id,
        "title": work.title,
        "doi": work.doi,
        "year": work.year,
        "type": work.work_type,
        "arxiv_id": work.arxiv_id,
        "author_names": [author.name for author in work.authors],
        "author_ids": work.author_ids,
    }


def _selected_work_id(selected_source: str, evidence) -> str | None:
    """Choose the selected work identifier for baseline output."""
    if selected_source == "doi_candidate" and evidence.doi_work:
        return evidence.doi_work.work_id
    if selected_source == "openalex_title_candidate" and evidence.title_work_candidates:
        return evidence.title_work_candidates[0].work_id
    if selected_source == "arxiv_candidate" and evidence.arxiv_candidates:
        return evidence.arxiv_candidates[0].arxiv_id
    return None


def _doi_status(assessment: str) -> str:
    """Classify DOI verification status for baseline output."""
    if assessment == "mismatch":
        return "present_mismatch"
    if assessment == "verified":
        return "present_verified"
    if assessment == "variant":
        return "present_title_variant"
    if assessment == "absent":
        return "absent"
    return "present_unchecked"


if __name__ == "__main__":
    main()
