from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.test_agent.stage_logging import LOG_MODE_ENV, StageLogger, get_log_mode

IMPORT_CONTRACT_SCRIPT = SCRIPT_DIR / "import_contract.py"
STAGE1_SCRIPT = SCRIPT_DIR / "stage1.py"
STAGE2_SCRIPT = SCRIPT_DIR / "stage2.py"
STAGE4_SCRIPT = SCRIPT_DIR / "stage4.py"
STAGE5_SCRIPT = SCRIPT_DIR / "stage5.py"
STAGE6_SCRIPT = SCRIPT_DIR / "stage6.py"
STAGE56_INTEGRATION_SCRIPT = SCRIPT_DIR / "stage56_integration.py"
STAGE7_SCRIPT = SCRIPT_DIR / "stage7.py"
E2E_SCRIPT = SCRIPT_DIR / "e2e_mvp.py"
PENDING_STAGE_SCRIPTS = [
    SCRIPT_DIR / "stage3.py",
]


AGGREGATED_STAGE_SCRIPTS = [
    IMPORT_CONTRACT_SCRIPT,
    STAGE1_SCRIPT,
    STAGE2_SCRIPT,
    STAGE4_SCRIPT,
    STAGE5_SCRIPT,
    STAGE6_SCRIPT,
    STAGE56_INTEGRATION_SCRIPT,
    STAGE7_SCRIPT,
    E2E_SCRIPT,
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CiteAnalyzer stage validations.")
    parser.add_argument("--log", choices=("brief", "detail"), default=None, help="Stage log verbosity.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    log_mode = args.log or get_log_mode()
    logger = StageLogger("aggregate", mode=log_mode)
    child_env = os.environ.copy()
    child_env[LOG_MODE_ENV] = log_mode

    for script in AGGREGATED_STAGE_SCRIPTS:
        logger.start(script.name)
        try:
            subprocess.run([sys.executable, str(script)], check=True, env=child_env)
        except subprocess.CalledProcessError as exc:
            logger.fail(script.name, detail=f"exit_code={exc.returncode}")
            raise
        logger.done(f"aggregate::{script.name}")

    print("Pending stage validation scripts:")
    for script in PENDING_STAGE_SCRIPTS:
        print(f"- TODO {script.name}")


if __name__ == "__main__":
    main()
