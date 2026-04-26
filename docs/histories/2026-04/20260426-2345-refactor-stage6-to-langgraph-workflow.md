## [2026-04-26 23:45] | Task: 将 stage6 改成 LangGraph 工作流

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `gpt-5`
- **Runtime**: `Codex CLI / PowerShell`

### 📥 User Query

> 选择方案 A：LangGraph 工作流 + 局部 agent。Node1 加载阶段5产物，Node2 判断是不是 TeX，Node3 TeX bibliography matcher，Node4 正文 citation finder，Node5 情感分类，Node6 聚合输出。请先修改计划文档，再实现。

### 🛠 Changes Overview

**Scope:** `docs/exec-plans/`, `packages/sentiment/`, `scripts/test_agent/`, `docs/histories/`

**Key Actions:**

- **更新计划文档**: 把阶段6（当前分支仍是旧编号文档）的实现建议改成 `LangGraph` 工作流 + 局部 agent。
- **新增 workflow 实现**: 用 `StateGraph` 串起 `load -> detect -> tex bibliography -> body citation -> classify -> aggregate`。
- **保留局部 agent**: LLM 继续负责高歧义判断，但步骤顺序由工作流固定。

### 🧠 Design Intent (Why)

stage6 的问题不是“模型不够聪明”，而是步骤太多、边界太模糊。把整体做成显式工作流后，定位 bibliograpy、citation key 和正文上下文就有了稳定轨道，LLM 只在局部决策点介入。

### 📁 Files Modified

- `docs/exec-plans/active/2026-04-26-stage5-citation-sentiment-agent.md`
- `packages/sentiment/workflow.py`
- `packages/sentiment/service.py`
- `packages/sentiment/models.py`
- `packages/sentiment/llm_locator.py`
- `packages/sentiment/reference_locator.py`
- `scripts/test_agent/stage6.py`
- `docs/histories/2026-04/20260426-2345-refactor-stage6-to-langgraph-workflow.md`
