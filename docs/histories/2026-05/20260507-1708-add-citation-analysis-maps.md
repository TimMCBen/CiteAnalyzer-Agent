## [2026-05-07 17:08] | Task: add citation analysis visual maps

### 🤖 Execution Context

- **Agent ID**: `Codex CLI session`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex + oh-my-codex`

### 📥 User Query

> 现在的每个阶段分别是干什么的，每个阶段的输入输出的能可视化的呈现一份给我吗？3个都要，并且保存一份在本地。

### 🛠 Changes Overview

**Scope:** `docs/design-docs/`, `docs/ARCHITECTURE.md`, `docs/histories/`

**Key Actions:**

- **新增阶段图谱文档**: 在 `docs/design-docs/citation-analysis-maps.md` 中整理了用户视角流程图、开发者视角状态演化图、实现视角代码路径图。
- **补充测试入口视图**: 追加当前默认验证入口与 `stage1/2/4/5/56/6/7/e2e` 的关系图。
- **导航同步**: 将新文档登记到设计文档索引，并从架构总览链接过去。

### 🧠 Design Intent (Why)

这份文档的目标不是替代 `ARCHITECTURE.md`，而是把“阶段职责、输入输出、状态演化、代码落点”从总览文档中抽出来，形成一份更适合讲解和 onboarding 的认知地图。

### 📁 Files Modified

- `docs/design-docs/citation-analysis-maps.md`
- `docs/design-docs/index.md`
- `docs/ARCHITECTURE.md`
