## [2026-05-17 13:05] | Task: 增加报告图表呈现

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI`

### 📥 User Query

> 检查报告呈现形式，判断哪些数据适合图表化，和多个智能体讨论后执行图表方案。

### 🛠 Changes Overview

**Scope:** 阶段 7 HTML 报告、阶段验证、架构与供应链说明

**Key Actions:**

- **[图表层]**: 在静态 HTML 报告中接入 ECharts，增加年份趋势、学者质量分布、引用情感分布、机构 Top N 图表容器。
- **[退化策略]**: 单年份、单情感桶、低基数机构等稀疏数据退化为摘要 / fallback，不伪装成趋势或满饼图。
- **[信息架构]**: 将数据质量提前为状态面板，`manual_attention_items` 改为摘要 + 折叠详情。
- **[契约保护]**: `report.json` 仍保留原始 `summary/charts/provenance/contexts`，图表 option 只在 HTML 展示层生成。

### 🧠 Design Intent (Why)

当前报告已经有结构化 chart payload，但 HTML 只显示列表。图表升级需要避免把低信息密度或语义不可靠的数据强行可视化，因此采用 ECharts + fallback，并把机构分布限定为 Top N 而不是地理地图。

### 📁 Files Modified

- `packages/reporting/service.py`
- `scripts/test_agent/stage7.py`
- `docs/ARCHITECTURE.md`
- `docs/testing/stage-validation.md`
- `docs/SUPPLY_CHAIN_SECURITY.md`
