"""Command-line validation helpers for stage logging."""
from __future__ import annotations

import os
from typing import Literal


LOG_MODE_ENV = "CITE_ANALYZER_STAGE_LOG"
LogMode = Literal["brief", "detail"]
VALID_LOG_MODES: tuple[LogMode, ...] = ("brief", "detail")


def get_log_mode() -> LogMode:
    """Return log mode for stage validation."""
    raw_mode = os.getenv(LOG_MODE_ENV, "brief").strip().lower()
    if raw_mode in VALID_LOG_MODES:
        return raw_mode  # type: ignore[return-value]
    allowed = ", ".join(VALID_LOG_MODES)
    raise ValueError(f"invalid {LOG_MODE_ENV}={raw_mode!r}; expected one of: {allowed}")


class StageLogger:
    """Store stage logger information used by stage validation."""
    def __init__(self, stage_name: str, mode: LogMode | None = None):
        self.stage_name = stage_name
        self.mode = mode or get_log_mode()

    def start(self, case_name: str | None = None) -> None:
        """Emit stage-start records for stage logger."""
        print(f"▶ START {self._target(case_name)}", flush=True)

    def pass_case(self, case_name: str, detail: str | None = None) -> None:
        """Emit passed-case records for stage logger."""
        suffix = f" | {detail}" if detail and self.mode == "detail" else ""
        print(f"✅ PASS {self._target(case_name)}{suffix}", flush=True)

    def detail(self, message: str) -> None:
        """Emit detailed progress log records for stage logger."""
        if self.mode == "detail":
            print(f"ℹ DETAIL {self.stage_name} | {message}", flush=True)

    def skip(self, case_name: str, reason: str) -> None:
        """Emit skipped-step log records for stage logger."""
        print(f"⏭ SKIP {self._target(case_name)} | reason={reason}", flush=True)

    def fail(self, case_name: str, detail: str | None = None) -> None:
        """Emit failure log records for stage logger."""
        suffix = f" | {detail}" if detail else ""
        print(f"❌ FAIL {self._target(case_name)}{suffix}", flush=True)

    def done(self, message: str | None = None) -> None:
        """Emit stage-completion records for stage logger."""
        suffix = f" | {message}" if message else ""
        print(f"✅ DONE {self.stage_name}{suffix}", flush=True)

    def _target(self, case_name: str | None) -> str:
        """Build the display target for a stage log event for stage logger."""
        if not case_name:
            return self.stage_name
        return f"{self.stage_name}::{case_name}"
