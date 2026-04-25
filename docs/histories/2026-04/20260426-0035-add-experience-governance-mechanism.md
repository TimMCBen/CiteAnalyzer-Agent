## [2026-04-26 00:35] | Task: 增加协作经验沉淀机制

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI + OMX guidance`

### 📥 User Query

> 好的，你可以写，请注意，这个机制应该作为一个项目无关的机制，我以后可以复用。

### 🛠 Changes Overview

**Scope:** `docs/`, `AGENTS.md`

**Key Actions:**

- **新增通用机制文档**: 新增 `docs/EXPERIENCE_GOVERNANCE.md`，定义“经验自动入池，规则升级人工确认”的通用机制。
- **补 AGENTS 入口**: 在 `AGENTS.md` 中加入简短触发规则和文档入口，不把完整机制正文塞进入口文件。
- **同步仓库协作约定**: 在 `docs/REPO_COLLAB_GUIDE.md` 中补一条引用，明确经验池与正式规则的边界。

### 🧠 Design Intent (Why)

这轮开发已经暴露出很多可复用的协作经验，但这些经验并不都适合直接升格成仓库长期规范。需要一套可跨项目复用的机制，允许经验自动沉淀，同时保留对初始基线文件和长期规范文件的人工把关。

### 📁 Files Modified

- `AGENTS.md`
- `docs/REPO_COLLAB_GUIDE.md`
- `docs/EXPERIENCE_GOVERNANCE.md`
- `docs/histories/2026-04/20260426-0035-add-experience-governance-mechanism.md`
