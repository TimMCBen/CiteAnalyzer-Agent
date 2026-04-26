## [2026-04-26 22:35] | Task: 提交 stage5 全文抓取基础

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `gpt-5`
- **Runtime**: `Codex CLI / PowerShell`

### 📥 User Query

> 先把 packages/sentiment/ 按 stage5 / stage6 分两批提交；再把 scripts/test_agent/stage5.py 和 stage6.py 整理成正式验证入口。

### 🛠 Changes Overview

**Scope:** `packages/sentiment/`, `scripts/test_agent/`, `docs/histories/`

**Key Actions:**

- **补 stage5 包基础**: 新增 `FullTextDocument` / `TextSourceSelection`，实现真实 `arXiv-first` 全文抓取、PDF/HTML/LaTeX 解析和本地落盘。
- **保留原始材料**: 对 `arXiv e-print` 同时保存 `parsed txt`、`source.tar` 和 `extracted/` 源文件树。
- **补正式验证入口**: 把 `scripts/test_agent/stage5.py` 收口成“全文抓取与落盘验证”脚本。

### 🧠 Design Intent (Why)

stage5 只负责“把全文材料拿下来并准备好”，不混入引用定位和情感判断。先把这条链路独立提交，后续 stage6 才能稳定消费同一份本地全文材料。

### 📁 Files Modified

- `packages/sentiment/__init__.py`
- `packages/sentiment/models.py`
- `packages/sentiment/fulltext.py`
- `scripts/test_agent/stage5.py`
- `docs/histories/2026-04/20260426-2235-add-stage5-fulltext-foundation.md`
