"""Shared stdout logger used by lightweight repository validation scripts."""
from __future__ import annotations

import os
from typing import Literal


LOG_MODE_ENV = "CITE_ANALYZER_STAGE_LOG"
LogMode = Literal["brief", "detail"]
VALID_LOG_MODES: tuple[LogMode, ...] = ("brief", "detail")


def get_log_mode() -> LogMode:
    """Resolve the stage-validation log mode from the environment."""
    raw_mode = os.getenv(LOG_MODE_ENV, "brief").strip().lower()
    if raw_mode in VALID_LOG_MODES:
        return raw_mode  # type: ignore[return-value]
    allowed = ", ".join(VALID_LOG_MODES)
    raise ValueError(f"invalid {LOG_MODE_ENV}={raw_mode!r}; expected one of: {allowed}")


class StageLogger:
    """Emit stable validation tokens while supporting brief and detail modes."""
    def __init__(self, stage_name: str, mode: LogMode | None = None):
        self.stage_name = stage_name
        self.mode = mode or get_log_mode()

    def start(self, case_name: str | None = None) -> None:
        """Emit a stage or case start record."""
        print(f"▶ START {self._target(case_name)}", flush=True)

    def pass_case(self, case_name: str, detail: str | None = None) -> None:
        """Emit a passed-case record with optional detail output."""
        suffix = f" | {detail}" if detail and self.mode == "detail" else ""
        print(f"✅ PASS {self._target(case_name)}{suffix}", flush=True)

    def detail(self, message: str) -> None:
        """Emit detail output only when detail mode is enabled."""
        if self.mode == "detail":
            print(f"ℹ DETAIL {self.stage_name} | {message}", flush=True)

    def skip(self, case_name: str, reason: str) -> None:
        """Emit a skipped-case record with a reason."""
        print(f"⏭ SKIP {self._target(case_name)} | reason={reason}", flush=True)

    def fail(self, case_name: str, detail: str | None = None) -> None:
        """Emit a failed-case record with optional detail."""
        suffix = f" | {detail}" if detail else ""
        print(f"❌ FAIL {self._target(case_name)}{suffix}", flush=True)

    def done(self, message: str | None = None) -> None:
        """Emit a stage-completion record."""
        suffix = f" | {message}" if message else ""
        print(f"✅ DONE {self.stage_name}{suffix}", flush=True)

    def _target(self, case_name: str | None) -> str:
        """Build a stable display target for a stage log event."""
        if not case_name:
            return self.stage_name
        return f"{self.stage_name}::{case_name}"
