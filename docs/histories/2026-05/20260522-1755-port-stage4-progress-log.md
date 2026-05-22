## [2026-05-22 17:55] | Task: 迁移阶段 4 作者画像进度日志

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI`

### 📥 User Query

> 不合并旧远程分支，改为把“阶段 4 进度日志”能力移植到当前 main，然后创建 PR 并用 gh 合并。

### 🛠 Changes Overview

**Scope:** RuntimeLogger、阶段 4 work-authorship 作者画像、测试入口、runtime logging contract、CI 阻断修复

**Key Actions:**

- **[进度日志]**: 为正式 `RuntimeLogger` 增加 `PROGRESS` 输出和固定宽度日志行式进度条。
- **[阶段 4 接入]**: 在当前 work-authorship / author-id 作者画像循环中输出作者处理进度、匹配数、弱证据数和失败累计。
- **[测试入口]**: 让 `scripts/test_agent/run.py --log` 同步设置正式 runtime 日志模式，避免聚合验证只影响测试 `StageLogger`。
- **[回归验证]**: 补充 detail / brief / quiet 三种模式下的阶段 4 进度日志 contract。
- **[CI 收口]**: 让 CI 中空 `API_KEY` 跳过 live LLM 国家解析，上调 OSV 报告的脆弱依赖下限，并让 markdownlint 排除导入型外部资料目录。

### 🧠 Design Intent (Why)

旧远程分支里的进度条基于已经废弃的作者名搜索和 DBLP fallback 路径，直接合并会倒退 Stage 4 的身份可信度策略。本次只迁移可观测性能力，把进度日志挂到当前可信的 OpenAlex work-authorship / author-id 链路上。

### 📁 Files Modified

- `packages/shared/runtime_logging.py`
- `packages/author_intel/service.py`
- `scripts/test_agent/run.py`
- `scripts/test_agent/run_contract.py`
- `scripts/test_agent/runtime_logging_contract.py`
- `scripts/test_agent/stage7.py`
- `requirements-ci.txt`
- `Thesis_Crawling_and_Filtering_System/requirements.txt`
- `.github/workflows/ci.yml`
- `.markdownlint.json`
- `docs/CICD.md`
- `风险.md`
- `docs/exec-plans/active/2026-05-16-runtime-log-chinese-readability.md`
- `docs/histories/2026-05/20260522-1755-port-stage4-progress-log.md`
