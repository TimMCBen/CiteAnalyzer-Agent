## [2026-05-19 20:49] | Task: 精化 Stage 7 报告展示

### 🤖 Execution Context

- **Agent ID**: `codex`
- **Base Model**: `gpt-5.4`
- **Runtime**: `Codex CLI`

### 📥 User Query

> 按已批准计划执行：删除报告中不合适的说明文案，明确学者标签规则，调整机构分布排序，并把代表性引用语境改成带施引论文标题、折叠引用内容和自然中文“原因”的展示方式。

### 🛠 Changes Overview

**Scope:** Stage 7 报告生成、Stage 6 情感分类提示词、测试合同。

**Key Actions:**

- **[Report wording]**: 删除“；不伪装成趋势图”和 GeoJSON 技术措辞，改成面向用户的说明。
- **[Scholar rule display]**: 在学者质量分布说明中明确 `work-authorship`、`h-index >= 30` 和 `frequency >= 2` 规则。
- **[Context display]**: 代表性引用语境补充施引论文标题、年份/DOI 元信息、折叠引用内容，并将展示原因清洗为自然中文。
- **[Prompt contract]**: 收紧情感分类 `evidence_note` 提示词，要求输出 1-2 句可直接接在“原因：”后的中文解释。

### 🧠 Design Intent (Why)

Stage 7 是最终交付页面，页面措辞不能暴露过多工程实现，也不能让引用证据难以阅读。本次改动把调试 evidence 与用户可读原因分离：JSON 保留原始 evidence，HTML 展示自然解释，减少误导和阅读负担。

### 📁 Files Modified

- `packages/reporting/service.py`
- `packages/sentiment/classifier.py`
- `scripts/test_agent/stage7.py`
- `scripts/test_agent/llm_prompt_contract.py`
