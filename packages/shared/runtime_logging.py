from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Literal


RUNTIME_LOG_MODE_ENV = "CITE_ANALYZER_RUNTIME_LOG"
RuntimeLogMode = Literal["quiet", "brief", "detail"]
VALID_RUNTIME_LOG_MODES: tuple[RuntimeLogMode, ...] = ("quiet", "brief", "detail")

_SENSITIVE_KEY_PARTS = ("api-key", "x-api-key", "key", "token", "authorization", "secret", "password")
_STAGE_LABELS = {
    "stage1": "阶段1",
    "stage2": "阶段2",
    "stage4": "阶段4",
    "stage5": "阶段5",
    "stage6": "阶段6",
    "stage7": "阶段7",
}


@dataclass(frozen=True)
class AnalysisRuntimeOptions:
    max_citations: int | None = None


class NoOpRuntimeLogger:
    mode: RuntimeLogMode = "quiet"

    def stage_start(self, stage: str, message: str, **fields: Any) -> None:
        return None

    def stage_done(self, stage: str, message: str, **fields: Any) -> None:
        return None

    def progress(self, stage: str, message: str, completed: int, total: int, **fields: Any) -> None:
        return None

    def detail(self, event: str, message: str, **fields: Any) -> None:
        return None

    def warn(self, event: str, message: str, **fields: Any) -> None:
        return None

    def skip(self, event: str, message: str, **fields: Any) -> None:
        return None

    def fail(self, event: str, message: str, **fields: Any) -> None:
        return None

    def summary(self, title: str = "分析结果摘要", **fields: Any) -> None:
        return None


class RuntimeLogger(NoOpRuntimeLogger):
    def __init__(self, component: str = "analyzer", mode: RuntimeLogMode | None = None):
        self.component = component
        self.mode = mode or get_runtime_log_mode()

    def stage_start(self, stage: str, message: str, **fields: Any) -> None:
        if self.mode != "quiet":
            self._print("▶", "START", _stage_label(stage), message, fields)

    def stage_done(self, stage: str, message: str, **fields: Any) -> None:
        if self.mode != "quiet":
            self._print("✅", "DONE", _stage_label(stage), message, fields)

    def progress(self, stage: str, message: str, completed: int, total: int, **fields: Any) -> None:
        if self.mode == "quiet":
            return
        if self.mode != "detail" and not _is_progress_milestone(completed, total):
            return
        self._print("📊", "PROGRESS", _stage_label(stage), f"{message} {_format_progress_bar(completed, total)}", fields)

    def detail(self, event: str, message: str, **fields: Any) -> None:
        if self.mode == "detail":
            self._print("ℹ", "DETAIL", event, message, fields)

    def warn(self, event: str, message: str, **fields: Any) -> None:
        self._print("⚠", "WARN", event, message, fields)

    def skip(self, event: str, message: str, **fields: Any) -> None:
        if self.mode != "quiet":
            self._print("⏭", "SKIP", event, message, fields)

    def fail(self, event: str, message: str, **fields: Any) -> None:
        self._print("❌", "FAIL", event, message, fields)

    def summary(self, title: str = "分析结果摘要", **fields: Any) -> None:
        if self.mode == "quiet" and fields.get("status") != "failed":
            return
        print(f"===== 📄 {title} =====", flush=True)
        for key, value in fields.items():
            print(f"{_summary_label(key)}: {_clean_value(key, value)}", flush=True)
        print("==========================", flush=True)

    def _print(self, icon: str, token: str, event: str, message: str, fields: dict[str, Any]) -> None:
        suffix = _format_fields(fields)
        print(f"{icon} {token} {event} | {message}{suffix}", flush=True)


_LOGGER: ContextVar[NoOpRuntimeLogger | RuntimeLogger | None] = ContextVar("cite_analyzer_runtime_logger", default=None)
_OPTIONS: ContextVar[AnalysisRuntimeOptions] = ContextVar(
    "cite_analyzer_runtime_options",
    default=AnalysisRuntimeOptions(),
)
_NOOP_LOGGER = NoOpRuntimeLogger()


def get_runtime_log_mode() -> RuntimeLogMode:
    raw_mode = os.getenv(RUNTIME_LOG_MODE_ENV, "brief").strip().lower()
    if raw_mode in VALID_RUNTIME_LOG_MODES:
        return raw_mode  # type: ignore[return-value]
    allowed = ", ".join(VALID_RUNTIME_LOG_MODES)
    raise ValueError(f"invalid {RUNTIME_LOG_MODE_ENV}={raw_mode!r}; expected one of: {allowed}")


def set_runtime_logger(logger: NoOpRuntimeLogger | RuntimeLogger) -> Token[NoOpRuntimeLogger | RuntimeLogger | None]:
    return _LOGGER.set(logger)


def reset_runtime_logger(token: Token[NoOpRuntimeLogger | RuntimeLogger | None]) -> None:
    _LOGGER.reset(token)


def get_runtime_logger() -> NoOpRuntimeLogger | RuntimeLogger:
    return _LOGGER.get() or _NOOP_LOGGER


def set_runtime_options(options: AnalysisRuntimeOptions) -> Token[AnalysisRuntimeOptions]:
    return _OPTIONS.set(options)


def reset_runtime_options(token: Token[AnalysisRuntimeOptions]) -> None:
    _OPTIONS.reset(token)


def get_runtime_options() -> AnalysisRuntimeOptions:
    return _OPTIONS.get()


@contextmanager
def runtime_context(
    logger: NoOpRuntimeLogger | RuntimeLogger | None = None,
    options: AnalysisRuntimeOptions | None = None,
) -> Iterator[NoOpRuntimeLogger | RuntimeLogger]:
    active_logger = logger or RuntimeLogger()
    logger_token = set_runtime_logger(active_logger)
    options_token = set_runtime_options(options or AnalysisRuntimeOptions())
    try:
        yield active_logger
    finally:
        reset_runtime_options(options_token)
        reset_runtime_logger(logger_token)


def _stage_label(stage: str) -> str:
    return _STAGE_LABELS.get(stage, stage)


def _format_fields(fields: dict[str, Any]) -> str:
    visible = [
        f"{key}={_clean_value(key, value)}"
        for key, value in fields.items()
        if value is not None
    ]
    if not visible:
        return ""
    return " | " + " ".join(visible)


def _format_progress_bar(current: int, total: int, width: int = 16) -> str:
    safe_total = max(1, int(total))
    safe_current = min(max(0, int(current)), safe_total)
    percent = round((safe_current / safe_total) * 100)
    filled = round(width * safe_current / safe_total)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}] {safe_current}/{safe_total} {percent}%"


def _is_progress_milestone(current: int, total: int) -> bool:
    if total <= 0 or current <= 0:
        return False
    if total <= 5 or current >= total:
        return True
    previous_bucket = ((current - 1) * 4) // total
    current_bucket = (current * 4) // total
    return current_bucket > previous_bucket


def _clean_value(key: str, value: Any) -> str:
    if _is_sensitive_key(key):
        return "[REDACTED]"
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple, set)):
        return ",".join(_clean_value(key, item) for item in value)
    text = str(value)
    if "s2k-" in text.lower():
        return "[REDACTED]"
    return text


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("_", "-")
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def _summary_label(key: str) -> str:
    labels = {
        "target": "目标论文",
        "citing_papers": "施引文献",
        "author_profiles": "作者画像",
        "fulltext": "全文获取",
        "grobid": "GROBID命中",
        "sentiment": "引用情感",
        "degradation": "降级说明",
        "report": "报告路径",
        "status": "流程状态",
        "reason": "原因说明",
        "next_step": "下一步建议",
    }
    return labels.get(key, key)
