## [2026-04-27 02:55] | Task: 补充 README 的运行与测试入口

### 🤖 Execution Context

- **Agent ID**: `Codex / Ralph session`
- **Base Model**: `gpt-5`
- **Runtime**: `OMX Ralph mode`

### 📥 User Query

> 在目前的 readme 中补充如何运行和测试的方法，文件目录，以及如何 grobid 如何安装(docker)。

### 🛠 Changes Overview

**Scope:** `README.md`、`docs/histories`

**Key Actions:**

- **[运行说明]**: 在 README 中补充 `.env` 最小配置、项目级入口和运行前提。
- **[测试说明]**: 增加聚合验证、单阶段验证和常用 live smoke 命令。
- **[目录说明]**: 把原本过于粗略的仓库结构改成更具体的文件目录导览。
- **[GROBID Docker]**: 增加 Docker 启动命令、健康检查和 `GROBID_API_URL` 配置示例。

### 🧠 Design Intent (Why)

当前 README 更偏项目介绍，缺少“新进入仓库后怎么跑”的可执行入口。补齐运行、测试、目录和 GROBID 安装说明后，README 才更像一个真正的入口文档，同时仍把更细的说明留给 `docs/testing/` 和 `docs/ARCHITECTURE.md`。

### 📁 Files Modified

- `README.md`
- `docs/histories/2026-04/20260427-0255-enrich-readme-run-test-grobid.md`
