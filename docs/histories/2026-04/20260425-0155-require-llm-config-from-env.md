## [2026-04-25 01:55] | Task: 收口模型配置来源

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI`

### 📥 User Query

> 对于第1条，你帮我改一版！但是我想要的是以后从.env里调内容，而不是写在config里面

### 🛠 Changes Overview

**Scope:** 总智能体配置加载

**Key Actions:**

- **移除代码默认模型名**: 不再在 `config.py` 中写死默认 `MODEL`
- **统一使用 .env**: `API_KEY`、`BASE_URL`、`MODEL` 均改为必须从 `.env` 读取
- **补齐显式报错**: 缺少任一关键配置项时，立即返回明确错误

### 🧠 Design Intent (Why)

避免配置来源分裂。模型选择、代理地址和密钥都应由环境配置统一控制，而不是部分放在代码默认值、部分放在 `.env`。

### 📁 Files Modified

- `apps/analyzer/config.py`
- `docs/histories/2026-04/20260425-0155-require-llm-config-from-env.md`
