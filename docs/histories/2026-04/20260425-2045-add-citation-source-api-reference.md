## [2026-04-25 20:45] | Task: 补充阶段 2 外部数据源参考文档

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI + OMX guidance`

### 📥 User Query

> 阶段二剩下的内容，尤其是核心两个客户端，你帮我在网上调研调研，应该如何搞？我和你一起开发。  
> 我现在的核心问题是，1.这些api是免费的吗？2.这些api有现成的调用方式吗 3.以上你的调研能不能写入文档。  
> 好的，可以写入reference。

### 🛠 Changes Overview

**Scope:** `docs/references/`, `docs/histories/`

**Key Actions:**

- **新增外部源参考**: 新增 `docs/references/citation-source-apis.md`，整理 `Semantic Scholar` 与 `Crossref` 的费用、调用方式和项目接入建议。
- **更新 references 索引**: 在 `docs/references/README.md` 中加入新文档入口。
- **沉淀阶段 2 边界判断**: 明确 `Semantic Scholar` 更适合作为主 citation source，`Crossref` 更适合作为 metadata enrichment source。

### 🧠 Design Intent (Why)

阶段 2 接下来最容易反复争论的不是代码细节，而是“这两个外部源到底该怎么分工”。先把免费性、官方能力边界、现成调用方式和项目接入建议沉淀到 references，可以减少后续实现时的反复试错。

### 📁 Files Modified

- `docs/references/citation-source-apis.md`
- `docs/references/README.md`
- `docs/histories/2026-04/20260425-2045-add-citation-source-api-reference.md`
