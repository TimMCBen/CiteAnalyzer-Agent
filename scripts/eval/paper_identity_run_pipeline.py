"""Run the rule-first paper identity pipeline over evaluation rows."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.citation_sources.models import CitingPaper
from packages.paper_identity.clients.arxiv import ArxivMetadataClient
from packages.paper_identity.clients.openalex_work import OpenAlexWorkClient
from packages.paper_identity.service import resolve_paper_identity


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL rows from an evaluation dataset."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def to_citing_paper(row: dict[str, Any]) -> CitingPaper:
    """Convert one evaluation row into a citing-paper model."""
    sample_id = str(row.get("canonical_id") or row.get("s2_paper_id") or row.get("title") or "").strip()
    return CitingPaper(
        canonical_id=sample_id,
        title=str(row.get("title") or "").strip(),
        doi=str(row.get("doi") or "").strip() or None,
        year=row.get("year") if isinstance(row.get("year"), int) else None,
        authors=[str(author) for author in list(row.get("authors") or []) if author],
        venue=str(row.get("venue") or "").strip() or None,
        abstract=str(row.get("abstract") or "").strip() or None,
        source_links={str(key): str(value) for key, value in dict(row.get("source_links") or {}).items() if value},
        source_names=[str(name) for name in list(row.get("source_names") or []) if name],
        source_specific_ids={str(key): str(value) for key, value in dict(row.get("source_specific_ids") or {}).items() if value},
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI options for the pipeline evaluation runner."""
    parser = argparse.ArgumentParser(description="Run rule-first paper identity pipeline on an evaluation JSONL file.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=Path("reports/eval/pipeline_predictions.jsonl"))
    parser.add_argument("--use-llm-review", action="store_true", help="Use configured gpt-5.4 only for ambiguous rule cases.")
    return parser.parse_args()


def main() -> None:
    """Write rule-first paper identity predictions for a dataset."""
    args = parse_args()
    rows = read_jsonl(args.dataset)
    papers = [to_citing_paper(row) for row in rows]
    openalex = OpenAlexWorkClient()
    arxiv = ArxivMetadataClient()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for paper in papers:
            before_openalex = openalex.http_attempt_count
            before_arxiv = arxiv.http_attempt_count
            decision = resolve_paper_identity(
                paper,
                openalex_client=openalex,
                arxiv_client=arxiv,
                use_llm_review=args.use_llm_review,
            )
            row = decision.to_log_dict()
            row["s2_paper_id"] = paper.canonical_id
            row["paper_identity_decision"] = _identity_label(row)
            row["llm_call_count"] = 1 if decision.llm_review else 0
            row["api_call_count"] = (openalex.http_attempt_count - before_openalex) + (arxiv.http_attempt_count - before_arxiv)
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(papers)} predictions to {args.out}")


def _identity_label(row: dict[str, Any]) -> str:
    """Map identity decisions to comparable evaluation labels."""
    confidence = row.get("paper_match_confidence")
    if confidence in {"high", "medium"}:
        return "same_paper"
    if confidence == "low":
        return "different_paper"
    return "unresolved"


if __name__ == "__main__":
    main()
