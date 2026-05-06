## [2026-05-05 20:40] | Task: tighten validation entrypoints and report provenance

### 🤖 Execution Context

- **Agent ID**: `Codex CLI session`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex + oh-my-codex`

### 📥 User Query

> 持续作为 CiteAnalyzer-Agent 仓库开发代理运行，优先沿真实 Python 多阶段链路推进代码、验证和文档闭环，不要停在一次性单点修改。

### 🛠 Changes Overview

**Scope:** `scripts/test_agent/`, `scripts/`, `packages/reporting/`, `apps/analyzer/`, `docs/`

**Key Actions:**

- **默认验证入口收口**: 把 `stage56_integration.py` 接入 `scripts/test_agent/run.py`，并新增 `run_contract.py` 锁定聚合脚本清单。
- **bash 项目入口修复**: 调整 `scripts/check-project.sh` 的解释器选择与 `python.exe` 路径转换，新增 `check_project_contract.py` 防止再次回退到错误解释器。
- **报告降级信号补齐**: 将 `fetch_summary`、`source_trace`、`state.errors`、弱标注 `confidence_note` 接入 stage7 报告，并增强 `stage7.py` 对 provenance / manual attention 的断言。
- **文档与计划同步**: 更新 README 与阶段测试文档，移动已完成的 MVP closure roadmap 到 `docs/exec-plans/completed/`。

### 🧠 Design Intent (Why)

先把默认验证 gate 与项目级入口修到“真实可跑”，再让 stage7 报告显式暴露上游降级与证据不足，避免 analyzer 主链路看似成功但实际不可审计。最后同步 README 与 execution plan 状态，减少后续 Agent 被过期文档误导。

### 📁 Files Modified

- `scripts/test_agent/run.py`
- `scripts/test_agent/run_contract.py`
- `scripts/check-project.sh`
- `scripts/test_agent/check_project_contract.py`
- `packages/reporting/service.py`
- `apps/analyzer/nodes.py`
- `scripts/test_agent/stage7.py`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/product-specs/citation-analysis-mvp.md`
- `docs/testing/stage-validation.md`
- `经验.md`
- `docs/exec-plans/completed/2026-05-04-mvp-closure-roadmap.md`
