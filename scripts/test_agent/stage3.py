"""Reserve Stage 3 validation for future supplemental-source checks."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.test_agent.stage_logging import StageLogger


def main() -> None:
    """Emit the current Stage 3 placeholder status."""
    logger = StageLogger("stage3")
    logger.start()
    logger.skip("google_scholar_validation", "TODO: stage3 remains reserved for supplemental source exploration")
    logger.done("stage3 TODO placeholder")


if __name__ == "__main__":
    main()
