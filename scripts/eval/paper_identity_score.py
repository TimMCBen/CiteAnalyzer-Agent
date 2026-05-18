"""Score paper identity predictions against a labeled gold dataset."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.paper_identity.clients.arxiv import normalize_arxiv_id


@dataclass
class ScoreSummary:
    """Aggregate paper identity evaluation metrics and call counts."""
    total_gold: int
    comparable_identity: int
    paper_identity_accuracy: float | None
    selected_work_accuracy: float | None
    doi_mismatch_precision: float | None
    doi_mismatch_recall: float | None
    abstention_rate: float | None
    llm_call_count: int
    api_call_count: int


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL rows with validation-friendly error messages."""
    rows: list[dict[str, Any]] = []
    if not path.exists():
        raise FileNotFoundError(path)
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number} is not valid JSONL") from exc
        if isinstance(row, dict):
            rows.append(row)
    return rows


def index_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index labeled or predicted rows by citing-paper identifier."""
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        sample_id = str(row.get("s2_paper_id") or row.get("citing_paper_id") or "").strip()
        if sample_id:
            indexed[sample_id] = row
    return indexed


def score_predictions(gold_rows: list[dict[str, Any]], prediction_rows: list[dict[str, Any]]) -> ScoreSummary:
    """Compare prediction rows against gold labels and metrics."""
    predictions = index_by_id(prediction_rows)
    identity_total = 0
    identity_correct = 0
    selected_work_total = 0
    selected_work_correct = 0
    doi_tp = 0
    doi_fp = 0
    doi_fn = 0
    abstained = 0
    llm_calls = 0
    api_calls = 0

    for gold in gold_rows:
        sample_id = str(gold.get("s2_paper_id") or gold.get("citing_paper_id") or "").strip()
        pred = predictions.get(sample_id, {})
        gold_identity = str(gold.get("gold_identity_label") or "").strip()
        pred_identity = str(pred.get("paper_identity_decision") or pred.get("identity_label") or "").strip()
        if gold_identity and gold_identity != "unresolved":
            identity_total += 1
            if pred_identity == gold_identity:
                identity_correct += 1

        gold_work = str(gold.get("gold_openalex_work_id") or gold.get("gold_arxiv_id") or "").strip()
        pred_work = str(pred.get("selected_work_id") or pred.get("selected_source_id") or "").strip()
        if gold_work:
            selected_work_total += 1
            if _work_ids_match(gold_work, pred_work):
                selected_work_correct += 1

        gold_doi = str(gold.get("gold_doi_status") or "").strip()
        pred_doi = str(pred.get("doi_status") or pred.get("doi_assessment") or "").strip()
        gold_mismatch = gold_doi == "present_mismatch"
        pred_mismatch = pred_doi == "present_mismatch" or pred_doi == "mismatch"
        if pred_mismatch and gold_mismatch:
            doi_tp += 1
        elif pred_mismatch and not gold_mismatch:
            doi_fp += 1
        elif gold_mismatch and not pred_mismatch:
            doi_fn += 1

        if pred_identity in {"", "uncertain", "unresolved"} or bool(pred.get("needs_manual_review")):
            abstained += 1
        llm_calls += int(pred.get("llm_call_count") or 0)
        api_calls += int(pred.get("api_call_count") or 0)

    return ScoreSummary(
        total_gold=len(gold_rows),
        comparable_identity=identity_total,
        paper_identity_accuracy=_ratio(identity_correct, identity_total),
        selected_work_accuracy=_ratio(selected_work_correct, selected_work_total),
        doi_mismatch_precision=_ratio(doi_tp, doi_tp + doi_fp),
        doi_mismatch_recall=_ratio(doi_tp, doi_tp + doi_fn),
        abstention_rate=_ratio(abstained, len(gold_rows)),
        llm_call_count=llm_calls,
        api_call_count=api_calls,
    )


def _ratio(numerator: int, denominator: int) -> float | None:
    """Compute safe rounded metric ratios for evaluation output."""
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _work_ids_match(gold_work: str, pred_work: str) -> bool:
    """Compare predicted and gold work identifiers across schemes."""
    if not pred_work:
        return False
    if gold_work == pred_work:
        return True
    gold_arxiv = normalize_arxiv_id(gold_work)
    pred_arxiv = normalize_arxiv_id(pred_work)
    if gold_arxiv and pred_arxiv:
        return gold_arxiv == pred_arxiv
    return False


def parse_args() -> argparse.Namespace:
    """Parse CLI options for paper identity scoring."""
    parser = argparse.ArgumentParser(description="Score paper identity evaluation predictions.")
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--pipeline", required=True, type=Path)
    parser.add_argument("--baseline", required=False, type=Path)
    parser.add_argument("--out-json", type=Path, default=Path("reports/eval/paper_identity_100_metrics.json"))
    return parser.parse_args()


def main() -> None:
    """Write JSON metrics for pipeline and optional baseline predictions."""
    args = parse_args()
    gold = read_jsonl(args.gold)
    metrics: dict[str, Any] = {
        "pipeline": score_predictions(gold, read_jsonl(args.pipeline)).__dict__,
    }
    if args.baseline:
        metrics["llm_baseline"] = score_predictions(gold, read_jsonl(args.baseline)).__dict__

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
