## [2026-05-17 17:50] | Task: 让 GitHub CI 真实运行阶段验证

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI`

### 📥 User Query

> GitHub 里面会做 CI，请重新规划提交。

### 🛠 Changes Overview

**Scope:** GitHub CI、阶段 6 fixture 验证、CI 依赖说明

**Key Actions:**

- **[CI 依赖]**: 新增 `requirements-ci.txt`，并在 GitHub CI 中安装最小测试依赖后再运行 `scripts/ci.sh`。
- **[安全下限]**: 将 CI 依赖范围设置到 OSV 报告的修复版本之后，避免新增依赖清单触发已知漏洞失败。
- **[阶段 6 测试边界]**: 将默认 `stage6.py` fixture 验证改为 fake reference matcher 和 fake sentiment classifier，不再依赖真实 LLM SDK、`.env` 或外部模型服务。
- **[E2E 测试边界]**: 将 `e2e_mvp.py` 的引用定位和情感分类也接入同一组 fake，避免 PR CI 在 E2E 聚合验证中回落到真实 LLM。
- **[文档说明]**: 在 README 中说明 `requirements-ci.txt` 只是 CI 最小测试依赖，不是完整运行时 lockfile。

### 🧠 Design Intent (Why)

PR 的 GitHub CI 应真实运行聚合验证，而不是通过跳过阶段 5/6 来规避缺失依赖。与此同时，基础 CI 不能要求真实 LLM API，因此阶段 6 的默认 fixture 必须保持离线、确定性，只把 live smoke 留给显式 opt-in 入口。

后续 CI 日志显示 E2E 聚合验证仍会经过总图的情感分析节点，并在默认分类器处尝试构建真实 LLM。修复方式不是跳过 E2E，而是在 E2E 内显式注入与阶段 6 fixture 相同的 fake 引用匹配器和 fake 情感分类器，让 PR CI 继续覆盖完整流程编排，同时保持离线可复现。

### 📁 Files Modified

- `.github/workflows/ci.yml`
- `requirements-ci.txt`
- `scripts/test_agent/stage6.py`
- `scripts/test_agent/e2e_mvp.py`
- `README.md`
- `docs/histories/2026-05/20260517-1750-align-github-ci-dependencies.md`
