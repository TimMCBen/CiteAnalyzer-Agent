## [2026-04-26 22:55] | Task: 提交 stage6 引用定位与情感分析

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `gpt-5`
- **Runtime**: `Codex CLI / PowerShell`

### 📥 User Query

> 先把 packages/sentiment/ 按 stage5 / stage6 分两批提交；再把 scripts/test_agent/stage5.py 和 stage6.py 整理成正式验证入口。

### 🛠 Changes Overview

**Scope:** `packages/sentiment/`, `scripts/test_agent/`, `.codex/skills/`, `docs/histories/`

**Key Actions:**

- **补 stage6 模型与入口**: 新增 `CitationContext` / `SentimentSummary` / `SentimentAnalysisResult` 以及 `analyze_citation_sentiments`。
- **补 tex/bib 定位逻辑**: 对 TeX 源优先利用 `.bib/.bbl/.tex` 恢复 bibliography entry 和 citation key，再回正文定位 `\\cite{...}`。
- **补正式验证入口**: 把 `scripts/test_agent/stage6.py` 收口成正式情感分析验证脚本，并加入 `citing-5` 的真实 smoke。

### 🧠 Design Intent (Why)

stage6 的职责是“拿到 stage5 的全文材料后，恢复目标论文的真实引用位置并判断态度”。如果只看扁平化文本，真实 arXiv TeX 论文里的引用链路很容易丢失；因此这批提交明确把 `.bib/.tex` 作为优先路径。

### 📁 Files Modified

- `packages/sentiment/__init__.py`
- `packages/sentiment/models.py`
- `packages/sentiment/reference_locator.py`
- `packages/sentiment/classifier.py`
- `packages/sentiment/service.py`
- `packages/sentiment/llm_locator.py`
- `scripts/test_agent/stage6.py`
- `.codex/skills/stage6-tex-citation/SKILL.md`
- `docs/histories/2026-04/20260426-2255-add-stage6-citation-location-and-sentiment.md`
