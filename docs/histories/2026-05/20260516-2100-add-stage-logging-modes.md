## [2026-05-16 21:00] | Task: add stage logging modes

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI`

### 📥 User Query

> 为每个阶段设置详细日志，并允许运行时选择详细日志或简略日志；日志输出可以用少量 emoji 和分段符号方便查看。

### 🛠 Changes Overview

**Scope:** `scripts/test_agent/`, `docs/testing/`, `README.md`

**Key Actions:**

- **[Logging]**: 新增统一阶段日志工具，支持 `brief` / `detail` 模式和稳定状态 token。
- **[Entrypoints]**: 为聚合入口增加 `--log` 参数，并让项目级入口通过 `CITE_ANALYZER_STAGE_LOG` 透传日志模式。
- **[Stage Scripts]**: 将阶段验证脚本迁移到统一日志输出，并补充 detail 调试字段。
- **[Docs]**: 更新 README、测试文档和执行计划，记录日志模式用法。

### 🧠 Design Intent (Why)

统一阶段日志可以让日常验证保持简洁，同时在调试失败时提供足够上下文。日志使用 emoji 只作为视觉辅助，仍保留 `START` / `PASS` / `FAIL` / `SKIP` / `DETAIL` 等稳定文本，避免影响 CI 和脚本化判断。

### 📁 Files Modified

- `scripts/test_agent/stage_logging.py`
- `scripts/test_agent/run.py`
- `scripts/test_agent/*.py`
- `README.md`
- `docs/testing/README.md`
- `docs/testing/stage-validation.md`
- `docs/exec-plans/active/2026-05-16-stage-logging-modes.md`
