## [2026-05-04 13:35] | Task: 实现 stage7 报告生成

### Execution Context

- **Agent ID**: `codex-main-session`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI + OMX ralph`

### User Query

> `$ralph` 按要求开发，并另外设置一个智能体检查开发进度，检查 docs 写文件的情况。

### Changes Overview

**Scope:** reporting / analyzer report node / stage7 validation / docs sync

**Key Actions:**

- **新增 reporting 包**: 实现 `packages/reporting/service.py`，导出 `ReportArtifact`、HTML/JSON 报告和结构化 chart payload。
- **接回 stage7 节点**: 在 analyzer 中新增 `generate_report_node`、`build_stage7_graph()`，并让 `run_analysis()` 默认跑到 stage7。
- **补报告级验证**: 把 `scripts/test_agent/stage7.py` 从占位改成 fixture 驱动的报告 contract 验证。
- **同步验证矩阵与计划进度**: 让 `run.py` 聚合 stage7，并更新 README、testing、architecture、主 MVP plan、roadmap。

### Design Intent (Why)

stage7 的目标不是在这一轮做复杂前端，而是先把“报告 contract”固定下来：输出什么、存到哪里、怎样被阶段测试验证。只有先有稳定的 HTML/JSON 报告产物，后面的 E2E 才能验证完整闭环，而不是只停留在 stage6 的中间状态。

### Files Modified

- `README.md`
- `apps/analyzer/graph.py`
- `apps/analyzer/main.py`
- `apps/analyzer/nodes.py`
- `docs/ARCHITECTURE.md`
- `docs/exec-plans/active/2026-04-24-citation-analysis-mvp.md`
- `docs/exec-plans/active/2026-05-04-mvp-closure-roadmap.md`
- `docs/histories/2026-05/20260504-1335-add-stage7-reporting.md`
- `docs/testing/stage-validation.md`
- `packages/reporting/__init__.py`
- `packages/reporting/service.py`
- `packages/shared/models.py`
- `scripts/test_agent/run.py`
- `scripts/test_agent/stage7.py`
