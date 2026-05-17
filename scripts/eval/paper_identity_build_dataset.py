from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_citing_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("fetch_result"), dict):
        rows = payload["fetch_result"].get("citing_papers") or []
    elif isinstance(payload, dict) and isinstance(payload.get("citing_papers"), list):
        rows = payload["citing_papers"]
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    return [row for row in rows if isinstance(row, dict)]


def normalize_sample(row: dict[str, Any], *, target: str) -> dict[str, Any]:
    sample_id = str(row.get("canonical_id") or row.get("paperId") or row.get("s2_paper_id") or row.get("title") or "").strip()
    return {
        "target": target,
        "s2_paper_id": sample_id,
        "canonical_id": sample_id,
        "title": row.get("title"),
        "doi": row.get("doi"),
        "year": row.get("year"),
        "authors": list(row.get("authors") or []),
        "venue": row.get("venue"),
        "abstract": row.get("abstract"),
        "source_links": dict(row.get("source_links") or {}),
        "source_names": list(row.get("source_names") or []),
        "source_specific_ids": dict(row.get("source_specific_ids") or {}),
        "gold_identity_label": "unresolved",
        "gold_selected_source": "unresolved",
        "gold_arxiv_id": None,
        "gold_doi_status": "unresolved",
        "gold_openalex_work_id": None,
        "gold_author_mappings": [],
        "gold_notes": "TODO: human review required; GPT output must not be treated as gold.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a paper identity evaluation JSONL template from collected citing papers.")
    parser.add_argument("--input", required=True, action="append", type=Path, help="Stage2/sample/report JSON containing citing papers.")
    parser.add_argument("--target", action="append", default=[], help="Target label matching each --input; defaults to input stem.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--out", type=Path, default=Path("data/eval/paper_identity_100/gold.template.jsonl"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, input_path in enumerate(args.input):
        target = args.target[index] if index < len(args.target) else input_path.stem
        for row in load_citing_rows(input_path):
            sample = normalize_sample(row, target=target)
            sample_id = str(sample["s2_paper_id"])
            if not sample_id or sample_id in seen:
                continue
            seen.add(sample_id)
            rows.append(sample)
            if len(rows) >= args.limit:
                break
        if len(rows) >= args.limit:
            break

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")
    print(f"wrote {len(rows)} samples to {args.out}")


if __name__ == "__main__":
    main()
