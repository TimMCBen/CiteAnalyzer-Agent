## [2026-05-18 12:45] | Task: Fix requests retry exception classification

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `gpt-5`
- **Runtime**: `Codex CLI`

### 📥 User Query

> 用测试脚本测试 arXiv 论文时发现流程失败；bug 修复请提交。

### 🛠 Changes Overview

**Scope:** `packages/shared`

**Key Actions:**

- **Retry fix**: 将 `requests.Timeout`、`requests.ConnectionError`、`requests.SSLError` 修正为 `requests.exceptions.*`。
- **Validation**: 重新运行网络重试合同和相关编译检查，确认超时/连接/TLS 错误会被正常分类为可重试错误。

### 🧠 Design Intent (Why)

真实 e2e smoke 中 arXiv 请求超时后进入重试分类，但当前环境的 `requests` 模块没有顶层 `SSLError` 属性，导致流程从可降级网络错误变成 `AttributeError`。修正到 `requests.exceptions` 后，重试层能按设计处理 transient network failures。

### 📁 Files Modified

- `packages/shared/network_retry.py`
