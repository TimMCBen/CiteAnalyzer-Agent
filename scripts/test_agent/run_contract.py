from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
RUN_SCRIPT = SCRIPT_DIR / "run.py"
EXPECTED_AGGREGATED_SCRIPTS = [
    "stage1.py",
    "stage2.py",
    "stage4.py",
    "stage5.py",
    "stage6.py",
    "stage56_integration.py",
    "stage7.py",
    "e2e_mvp.py",
]


def load_run_module():
    spec = importlib.util.spec_from_file_location("test_agent_run", RUN_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def assert_run_aggregates_expected_scripts() -> None:
    module = load_run_module()
    dispatched_scripts: list[str] = []

    def fake_run(command: list[str], *, check: bool) -> None:
        assert check is True
        dispatched_scripts.append(Path(command[1]).name)

    module.subprocess.run = fake_run

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        module.main()

    assert dispatched_scripts == EXPECTED_AGGREGATED_SCRIPTS, dispatched_scripts

    output = stdout.getvalue()
    assert "Pending stage validation scripts:" in output
    assert "- TODO stage3.py" in output


def main() -> None:
    assert_run_aggregates_expected_scripts()
    print("[PASS] run_contract::aggregates_expected_scripts")
    print("run contract validation passed")


if __name__ == "__main__":
    main()
