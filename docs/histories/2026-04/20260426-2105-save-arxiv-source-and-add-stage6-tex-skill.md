## [2026-04-26 21:05] | Task: 保存 arXiv 原始包并补阶段6 tex 技能

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `gpt-5`
- **Runtime**: `Codex CLI / PowerShell`

### 📥 User Query

> 阶段5最后需要主动调用工具，解压压缩包到本地；给阶段6写一个 skill，让阶段6模型知道遇到 tex 文章时如何先 grep 关键词、定位标题，再回正文找引文句子。

### 🛠 Changes Overview

**Scope:** `packages/sentiment/`, `.codex/skills/`, `docs/histories/`

**Key Actions:**

- **补阶段5落盘产物**: 真实 `arXiv e-print` 抓取后不只保存解析文本，还保存原始 `tar` 包和解压后的 `.tex` 文件树。
- **补阶段6 tex skill**: 新增本地 skill 文档，说明处理 `.tex` 论文时的定位流程。
- **同步阶段6提示**: 把 “先参考文献、再引文号、再正文窗口” 的 TeX 工作流写进 LLM 定位提示。

### 🧠 Design Intent (Why)

如果阶段5只留下扁平化文本，阶段6很难在真实 TeX 论文里稳定恢复引用链路。保留原始包和解压目录后，阶段6就有机会回到源文件级别做更可靠的定位。

### 📁 Files Modified

- `packages/sentiment/models.py`
- `packages/sentiment/fulltext.py`
- `packages/sentiment/llm_locator.py`
- `packages/sentiment/service.py`
- `.codex/skills/stage6-tex-citation/SKILL.md`
- `docs/histories/2026-04/20260426-2105-save-arxiv-source-and-add-stage6-tex-skill.md`
