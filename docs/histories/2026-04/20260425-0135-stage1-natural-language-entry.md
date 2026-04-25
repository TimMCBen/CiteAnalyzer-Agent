## [2026-04-25 01:35] | Task: 完成阶段1自然语言入口骨架

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI`

### 📥 User Query

> 阶段 1 按“自然语言输入”这条新思路重写并执行；阶段一提交一版！

### 🛠 Changes Overview

**Scope:** 阶段 1 总智能体入口与执行计划

**Key Actions:**

- **重写阶段 1 计划**: 将 active plan 的阶段 1 从“字段输入解析”调整为“自然语言输入理解与状态初始化”
- **建立共享对象**: 新增 `UserQuery`、`TargetPaper`、`ParsedUserIntent`、`AnalysisState`
- **建立总智能体骨架**: 新增 `apps/analyzer` 入口、状态图和自然语言解析节点
- **接入模型配置**: 从 `.env` 读取 `API_KEY`、`BASE_URL`、`MODEL`
- **实现降级策略**: 在 LLM 失败时回退到规则解析
- **完成本地验证**: 用多条自然语言样本验证解析行为

### 🧠 Design Intent (Why)

阶段 1 不再把系统入口设计成“直接输入 DOI / 标题 / 论文 ID 的硬编码接口”，而是改为更符合整体产品定位的自然语言入口，让 `论文被引分析智能体` 先理解用户意图，再初始化标准化状态对象。

### 📁 Files Modified

- `apps/analyzer/__init__.py`
- `apps/analyzer/config.py`
- `apps/analyzer/graph.py`
- `apps/analyzer/main.py`
- `apps/analyzer/nodes.py`
- `packages/shared/__init__.py`
- `packages/shared/errors.py`
- `packages/shared/models.py`
- `docs/exec-plans/active/2026-04-24-citation-analysis-mvp.md`
- `docs/histories/2026-04/20260425-0135-stage1-natural-language-entry.md`

---

## [2026-04-25 02:10] | Task: 跟进评审反馈补强解析回退

### 📥 User Query

> @codex address that feedback (path=apps/analyzer/nodes.py line=45 side=RIGHT)

### 🛠 Changes Overview

**Scope:** `apps/analyzer` 阶段 1 输入解析鲁棒性

**Key Actions:**

- **新增二次回退判定**: 当 LLM 判定为 `citation_analysis` 但未提取具体句柄（`unknown/title`）且原文含 DOI/arXiv/OpenAlex 线索时，触发规则解析二次重试
- **合并解析结果**: 在规则解析命中具体句柄后，优先采用规则产出的 `paper_query/paper_query_type`，同时保留 LLM 提取出的 `analysis_goal/constraints`

### 🧠 Design Intent (Why)

评审指出当前逻辑仅在“非 citation_analysis”时回退，导致 LLM 漏抽具体 ID 时会把本可确定的请求误保留为 `uncertain`。本次补强用于优先保障目标论文句柄识别准确率，同时不丢失 LLM 对分析目标和约束的理解能力。

### 📁 Files Modified

- `apps/analyzer/nodes.py`
- `docs/histories/2026-04/20260425-0135-stage1-natural-language-entry.md`
