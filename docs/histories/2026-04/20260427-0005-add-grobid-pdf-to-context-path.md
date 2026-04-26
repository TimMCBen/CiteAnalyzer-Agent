## [2026-04-27 00:05] | Task: 接入 GROBID PDF 引文上下文路径

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `gpt-5`
- **Runtime**: `Codex CLI / PowerShell`

### 📥 User Query

> 把 GROBID 正式落成代码；做成 PDF 输入 -> XML -> 引用上下文，并接到 stage6 里，然后测速度。

### 🛠 Changes Overview

**Scope:** `apps/analyzer/`, `packages/sentiment/`, `scripts/test_agent/`, `.env`, `docs/histories/`

**Key Actions:**

- **新增 GROBID 客户端**: 增加本地 GROBID 服务健康检查与 `processFulltextDocument` 调用封装。
- **新增 TEI 后处理**: 从 GROBID TEI XML 中恢复目标参考文献条目和正文引文上下文。
- **接入 stage6 workflow**: 给 PDF 来源增加 GROBID 节点，形成 `PDF -> XML -> 引文上下文 -> 情感分类` 路径。
- **补烟测**: 在 `stage6.py` 中新增 `citing-5` 的 GROBID smoke，并记录耗时。

### 🧠 Design Intent (Why)

GROBID 已经能够把 PDF 的参考文献条目与正文引文标记结构化出来，比直接对 PDF 抽纯文本更适合作为阶段6的上下文提取底座。把它正式接进 stage6 后，PDF 来源和 TeX 来源都能走“先定位引文，再做情感”的统一路线。

### 📁 Files Modified

- `apps/analyzer/config.py`
- `packages/sentiment/grobid_client.py`
- `packages/sentiment/grobid_context.py`
- `packages/sentiment/fulltext.py`
- `packages/sentiment/workflow.py`
- `packages/sentiment/__init__.py`
- `scripts/test_agent/stage6.py`
- `.env`
- `docs/histories/2026-04/20260427-0005-add-grobid-pdf-to-context-path.md`
