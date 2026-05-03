## [2026-05-04 12:40] | Task: 接回 stage4/5/6 到 analyzer 总控

### Execution Context

- **Agent ID**: `codex-main-session`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI + OMX ralph`

### User Query

> `$ralph` 按要求开发，并另外设置一个智能体检查开发进度，检查 docs 写文件的情况。

### Changes Overview

**Scope:** analyzer orchestration / shared state glue / integration smoke / docs sync

**Key Actions:**

- **扩展 analyzer 状态**: 为 scholar、fulltext、sentiment 结果补齐 `AnalysisState` 字段。
- **接回 stage4/5/6**: 在 `apps/analyzer/nodes.py`、`graph.py`、`main.py` 中新增 author-intel、fulltext、sentiment 节点和默认 stage6 总控入口。
- **补集成烟测**: 新增 `scripts/test_agent/stage56_integration.py`，验证节点顺序和状态写回 glue。
- **同步仓库文档**: 更新 README、testing、architecture、主 MVP plan 和 roadmap 的当前进度。

### Design Intent (Why)

这一步的目标不是扩展领域逻辑，而是把已经独立可跑的 stage4、stage5、stage6 contract 稳定接回 analyzer。先把编排顺序、共享状态字段和降级路径固定下来，后续 stage7 报告层才能建立在真实总控输出上，而不是继续消费半成品脚本结果。

### Files Modified

- `README.md`
- `apps/analyzer/graph.py`
- `apps/analyzer/main.py`
- `apps/analyzer/nodes.py`
- `docs/ARCHITECTURE.md`
- `docs/exec-plans/active/2026-04-24-citation-analysis-mvp.md`
- `docs/exec-plans/active/2026-05-04-mvp-closure-roadmap.md`
- `docs/histories/2026-05/20260504-1240-integrate-stage456-into-analyzer.md`
- `docs/testing/stage-validation.md`
- `packages/author_intel/__init__.py`
- `packages/author_intel/service.py`
- `packages/shared/models.py`
- `scripts/test_agent/stage56_integration.py`
