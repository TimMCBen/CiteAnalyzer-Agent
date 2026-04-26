## [2026-04-27 00:15] | Task: 高亮目标引文

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `gpt-5`
- **Runtime**: `Codex CLI / PowerShell`

### 📥 User Query

> 当上下文里有多个引文时，把当前要分析的目标引文位置显式标出来，比如用 `**...**` 包裹，并在模型提示词里说明这一点。

### 🛠 Changes Overview

**Scope:** `packages/sentiment/`, `docs/histories/`

**Key Actions:**

- **GROBID 路径高亮**: 在包含多个 `ref type=\"bibr\"` 的段落中，把目标引文渲染成 `**[73]**` 这样的显式标记。
- **TeX 路径高亮**: 在 `\\cite{key}` 命中的上下文中，把目标 cite 包成 `**\\cite{key}**`。
- **更新提示词**: 明确告诉情感分类模型，`**...**` 是当前要判断的目标引文锚点。

### 🧠 Design Intent (Why)

当一个段落里有多个引文时，仅返回整段会让模型不知道到底要围绕哪个引文做判断。显式标记目标引文能显著减少多引文场景下的歧义。

### 📁 Files Modified

- `packages/sentiment/classifier.py`
- `packages/sentiment/grobid_context.py`
- `packages/sentiment/llm_locator.py`
- `docs/histories/2026-04/20260427-0015-highlight-target-citation-in-context.md`
