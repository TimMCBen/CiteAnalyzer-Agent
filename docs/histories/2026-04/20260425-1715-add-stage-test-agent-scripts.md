## [2026-04-25 17:15] | Task: 增加分阶段测试脚本入口

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI + OMX guidance`

### 📥 User Query

> 在仓库里增加 `scripts/test_agent/`，先补阶段 1 的测试脚本，其它阶段先留 TODO，并把 plan 一起更新；最后提交到远程。

### 🛠 Changes Overview

**Scope:** `scripts/`, `docs/`

**Key Actions:**

- **新增阶段测试目录**: 增加 `scripts/test_agent/`，提供阶段 1 可执行验证脚本和阶段 2 到阶段 7 的 TODO 占位脚本。
- **接入仓库级验证入口**: 新增 `scripts/test_agent/run.py` 并接入 `scripts/ci.sh` 与 `Makefile`。
- **同步计划与文档**: 在 active execution plan 中为各阶段加入测试脚本任务，并更新 CI/CD 文档。

### 🧠 Design Intent (Why)

当前仓库已经按阶段推进 MVP，但验证仍主要停留在手工记录里。把阶段验证沉淀成 `scripts/test_agent/` 下的可运行脚本，可以先把阶段 1 的行为锁住，同时给后续阶段保留统一入口，避免每推进一阶段都重新发明验证方式。

### 📁 Files Modified

- `scripts/test_agent/stage1.py`
- `scripts/test_agent/stage2.py`
- `scripts/test_agent/stage3.py`
- `scripts/test_agent/stage4.py`
- `scripts/test_agent/stage5.py`
- `scripts/test_agent/stage6.py`
- `scripts/test_agent/stage7.py`
- `scripts/test_agent/run.py`
- `scripts/ci.sh`
- `Makefile`
- `docs/CICD.md`
- `docs/exec-plans/active/2026-04-24-citation-analysis-mvp.md`
- `docs/histories/2026-04/20260425-1715-add-stage-test-agent-scripts.md`
