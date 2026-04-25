## [2026-04-25 22:35] | Task: 保存阶段 2 在线样本并切换默认入口

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI + OMX guidance`

### 📥 User Query

> 你现在就只测试一篇文章，测试一次，去实现现在的功能，把json文件保存下来。  
> 好的，现在完成剩下的内容。

### 🛠 Changes Overview

**Scope:** `apps/`, `docs/generated/`, `docs/exec-plans/`, `docs/histories/`

**Key Actions:**

- **保存真实在线样本**: 将阶段 2 对 DOI `10.1145/3368089.3409740` 的在线抓取结果保存到 `docs/generated/`。
- **切换默认运行路径**: 让 `run_analysis()` 默认走阶段 2，同时保留 `run_stage1_analysis()` 作为显式阶段 1 入口。
- **同步阶段状态**: 在阶段 2 计划和 generated 文档中记录当前在线验证结果。

### 🧠 Design Intent (Why)

阶段 2 既然已经能对真实 DOI 跑通，就应该把这次真实样本沉淀成可追溯产物，而不是只存在终端输出里。同时，默认运行入口继续停在阶段 1 已经不符合当前实现进度，因此将默认路径切到阶段 2，更符合仓库现状。

### 📁 Files Modified

- `apps/analyzer/main.py`
- `docs/generated/README.md`
- `docs/generated/stage2-live-10.1145.3368089.3409740.json`
- `docs/exec-plans/active/2026-04-25-stage2-citation-fetch-agent.md`
- `docs/histories/2026-04/20260425-2235-save-stage2-live-sample-and-promote-default-path.md`
