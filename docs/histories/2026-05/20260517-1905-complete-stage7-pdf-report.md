## [2026-05-17 19:05] | Task: 完整化 Stage 7 可交付报告

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI`

### 📥 User Query

> 另写一个 PDF 界面；不确定的东西调用大模型帮我查，比如国家匹配。

### 🛠 Changes Overview

**Scope:** Stage 7 reporting / PDF / country resolution / tests / docs

**Key Actions:**

- **[独立 PDF]**: 新增独立 PDF renderer，不通过 Playwright 或浏览器打印 HTML。
- **[报告结构]**: 增加分析摘要、重要学者表格、代表性引用语境。
- **[图表语义]**: HTML 情感图改为饼图，新增国家/地区分布与机构分布，保留 `source_map` 兼容字段。
- **[国家解析]**: 新增规则优先、LLM 可选的国家/地区解析路径，并记录 method / confidence / evidence trace。
- **[测试]**: Stage 7 contract 覆盖 PDF、pie chart、country / institution distribution，并强制真实调用模型验证国家解析；缺少 `API_KEY` / `BASE_URL` / `MODEL` 时测试失败。

### 🧠 Design Intent (Why)

课程题目要求“完整可视化分析报告”和 PDF 报告生成。用户明确不希望用浏览器打印 HTML，因此采用 `reportlab` 生成独立 PDF 版式；国家/地区识别存在不确定性，所以用规则处理高置信机构，对不确定机构保留 LLM 辅助路径和可复核 trace。

### 📁 Files Modified

- `packages/reporting/service.py`
- `packages/reporting/pdf_renderer.py`
- `packages/reporting/country_resolution.py`
- `scripts/test_agent/stage7.py`
- `apps/analyzer/nodes.py`
- `requirements-ci.txt`
- `README.md`
- `docs/testing/stage-validation.md`
- `docs/histories/2026-05/20260517-1905-complete-stage7-pdf-report.md`
