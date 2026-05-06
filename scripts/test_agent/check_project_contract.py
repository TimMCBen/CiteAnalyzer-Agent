from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK_PROJECT_SCRIPT = REPO_ROOT / "scripts" / "check-project.sh"


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


def main() -> None:
    assert_check_project_prefers_python_exe_before_python3()
    print("[PASS] check_project_contract::prefers_python_exe_before_python3")
    print("check-project contract validation passed")


if __name__ == "__main__":
    main()
