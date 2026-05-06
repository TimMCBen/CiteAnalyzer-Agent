## [2026-04-29 14:35] | Task: 补充变更完成默认检查要求

### 🤖 Execution Context

- **Agent ID**: `not exposed in current runtime`
- **Base Model**: `Codex (GPT-5)`
- **Runtime**: `Codex CLI`

### 📥 User Query

> 提交 `AGENTS.md`，并使用与当前不同的分支名。

### 🛠 Changes Overview

**Scope:** `repo-docs`

**Key Actions:**

- **[AGENTS 约束补充]**: 为仓库根 `AGENTS.md` 增加“变更完成默认要求”段落，要求 Agent 在结束前检查 history、execution plan、可靠性/安全同步与经验沉淀。
- **[History 同步]**: 为本次文档改动新增对应的 `docs/histories/` 记录，满足仓库历史记录规范。

### 🧠 Design Intent (Why)

把“完成改动后还要检查什么”显式写进仓库级入口约束里，降低后续 Agent 漏掉 history、计划或安全同步检查的概率，同时保证这次文档变更本身可追溯。

### 📁 Files Modified

- `AGENTS.md`
- `docs/histories/2026-04/20260429-1435-add-agents-default-completion-checks.md`
