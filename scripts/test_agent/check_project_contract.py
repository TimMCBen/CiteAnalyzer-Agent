"""Validate the repository-level check-project shell wrapper."""
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK_PROJECT_SCRIPT = REPO_ROOT / "scripts" / "check-project.sh"

import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.test_agent.stage_logging import StageLogger


def assert_check_project_prefers_python_exe_before_python3() -> None:
    script_text = CHECK_PROJECT_SCRIPT.read_text(encoding="utf-8")

    python_exe_probe = 'command -v python.exe'
    python3_probe = 'command -v python3'
    python_exe_assignment = 'python_cmd="python.exe"'
    wslpath_conversion = 'run_script="$(wslpath -w "$run_script")"'
    cygpath_conversion = 'run_script="$(cygpath -w "$run_script")"'

    assert python_exe_probe in script_text, python_exe_probe
    assert python_exe_assignment in script_text, python_exe_assignment
    assert script_text.index(python_exe_probe) < script_text.index(python3_probe)
    assert wslpath_conversion in script_text or cygpath_conversion in script_text


def assert_check_project_does_not_override_stage_log_env() -> None:
    script_text = CHECK_PROJECT_SCRIPT.read_text(encoding="utf-8")
    assert "CITE_ANALYZER_STAGE_LOG=" not in script_text
    assert '"${python_cmd}" "${run_script}"' in script_text


def main() -> None:
    """Run check-project wrapper contract assertions."""
    logger = StageLogger("check_project_contract")
    logger.start()
    assert_check_project_prefers_python_exe_before_python3()
    logger.pass_case(
        "prefers_python_exe_before_python3",
        detail="checks=python.exe_order,wslpath_or_cygpath",
    )
    assert_check_project_does_not_override_stage_log_env()
    logger.pass_case("preserves_stage_log_env", detail="CITE_ANALYZER_STAGE_LOG not assigned by shell wrapper")
    logger.done("check-project contract validation passed")


if __name__ == "__main__":
    main()
