## [2026-04-29 02:05] | Task: 改进 stage5/stage6 的论文下载失败恢复

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI in repo workspace`

### 📥 User Query

> 按照上述 plan 执行，探索 5、6；如果有下载不了的论文，请给一个好的解决方案。

### 🛠 Changes Overview

**Scope:** `packages/sentiment/`, `scripts/test_agent/`, `README.md`, `docs/testing/`

**Key Actions:**

- **[补下载失败证据链]**: 在 `stage5` 的全文选择逻辑里记录下载尝试失败摘要，并把恢复建议拼进 `evidence_note`。
- **[提供可执行恢复方案]**: 当正文拿不到时，优先建议检查 DOI 落地页、作者 PDF / 预印本，或手动补 `source_links`；若摘要可用则自动回退到摘要。
- **[补回归测试]**: 为 `stage5` 增加“正文不可获取时仍返回恢复建议”的本地夹具验证，并同步更新 `stage6` 对 `unknown` 证据说明的断言。
- **[同步入口文档]**: 在 README 和测试说明里补上“下载失败恢复 + 摘要回退”的当前行为说明。

### 🧠 Design Intent (Why)

原来的 `stage5` 在抓不到全文时只会静默继续，最后让 `stage6` 收到一个笼统的 `no_text_available`。这对调试和人工补救都太弱。目标不是盲目再加更多下载源，而是先把失败原因和恢复路径显式暴露出来，让用户知道下一步该检查什么，并且在正文不可得时尽量保留摘要级分析能力。

### 📁 Files Modified

- `packages/sentiment/models.py`
- `packages/sentiment/fulltext.py`
- `scripts/test_agent/stage5.py`
- `scripts/test_agent/stage6.py`
- `README.md`
- `docs/testing/stage-validation.md`
