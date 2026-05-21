"""Run the opt-in live analyzer smoke test against external services."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.analyzer.main import run_analysis


DEFAULT_TARGET = "https://arxiv.org/pdf/2507.19457"


def main() -> None:
    """Run live analysis and assert all report artifacts are created."""
    parser = argparse.ArgumentParser(description="Opt-in live smoke for Chinese runtime logs.")
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--max-citations", type=int, default=3)
    parser.add_argument("--log", choices=("quiet", "brief", "detail"), default="detail")
    args = parser.parse_args()

    state = run_analysis(
        f"请分析这篇论文的被引情况：{args.target}",
        runtime_log_mode=args.log,
        max_citations=args.max_citations,
    )

    if state.get("status") != "report_generated":
        raise AssertionError(f"expected report_generated, got {state.get('status')}")
    artifact = state.get("report_artifact")
    if artifact is None:
        raise AssertionError("missing report_artifact")
    html_path = Path(artifact.export_paths["html"])
    json_path = Path(artifact.export_paths["json"])
    pdf_path = Path(artifact.export_paths["pdf"])
    if not html_path.exists() or not json_path.exists() or not pdf_path.exists():
        raise AssertionError(f"missing report files: html={html_path} json={json_path} pdf={pdf_path}")
    print(f"✅ DONE e2e_real_smoke | html={html_path} json={json_path} pdf={pdf_path}", flush=True)


if __name__ == "__main__":
    main()
