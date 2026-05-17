from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
RUN_SCRIPT = SCRIPT_DIR / "run.py"
EXPECTED_AGGREGATED_SCRIPTS = [
    "import_contract.py",
    "llm_prompt_contract.py",
    "network_retry_contract.py",
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
    dispatched_modes: list[str | None] = []

    def fake_run(command: list[str], *, check: bool, env=None) -> None:
        assert check is True
        dispatched_scripts.append(Path(command[1]).name)
        dispatched_modes.append((env or {}).get("CITE_ANALYZER_STAGE_LOG"))

    module.subprocess.run = fake_run

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        module.main([])

    assert dispatched_scripts == EXPECTED_AGGREGATED_SCRIPTS, dispatched_scripts
    assert dispatched_modes == ["brief"] * len(EXPECTED_AGGREGATED_SCRIPTS), dispatched_modes

    output = stdout.getvalue()
    assert "START aggregate::import_contract.py" in output
    assert "DONE aggregate" in output
    assert "Pending stage validation scripts:" in output
    assert "- TODO stage3.py" in output


def assert_run_detail_mode_overrides_environment() -> None:
    module = load_run_module()
    dispatched_modes: list[str | None] = []

    def fake_run(command: list[str], *, check: bool, env=None) -> None:
        _ = command
        assert check is True
        dispatched_modes.append((env or {}).get("CITE_ANALYZER_STAGE_LOG"))

    module.subprocess.run = fake_run
    original_mode = os.environ.get("CITE_ANALYZER_STAGE_LOG")
    os.environ["CITE_ANALYZER_STAGE_LOG"] = "brief"
    try:
        module.main(["--log", "detail"])
    finally:
        if original_mode is None:
            os.environ.pop("CITE_ANALYZER_STAGE_LOG", None)
        else:
            os.environ["CITE_ANALYZER_STAGE_LOG"] = original_mode

    assert dispatched_modes == ["detail"] * len(EXPECTED_AGGREGATED_SCRIPTS), dispatched_modes


def assert_run_rejects_invalid_cli_mode() -> None:
    module = load_run_module()
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        try:
            module.main(["--log", "noisy"])
        except SystemExit as exc:
            assert exc.code != 0
        else:
            raise AssertionError("expected invalid --log mode to exit non-zero")
    assert "invalid choice" in stderr.getvalue()


def main() -> None:
    if str(SCRIPT_DIR.parents[1]) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR.parents[1]))
    from scripts.test_agent.stage_logging import StageLogger

    logger = StageLogger("run_contract")
    logger.start()
    assert_run_aggregates_expected_scripts()
    logger.pass_case(
        "aggregates_expected_scripts",
        detail=f"scripts={EXPECTED_AGGREGATED_SCRIPTS} mode=brief",
    )
    assert_run_detail_mode_overrides_environment()
    logger.pass_case("detail_mode_overrides_environment", detail="cli=detail env_before=brief child_env=detail")
    assert_run_rejects_invalid_cli_mode()
    logger.pass_case("rejects_invalid_cli_mode", detail="cli=noisy rejected=True")
    logger.done("run contract validation passed")


if __name__ == "__main__":
    main()
