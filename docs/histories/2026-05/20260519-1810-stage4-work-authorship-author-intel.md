## [2026-05-19 18:10] | Task: Stage 4 work-authorship author intelligence

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI / PowerShell`

### 📥 User Query

> 下一步改 Stage 4：对每篇施引论文先 resolve OpenAlex work，若论文匹配高/中置信并有 work.authorships.author.id，就用这些 author IDs 拉作者画像；只有 work 不可信或无 authorship 时，这种情况就直接在日志中写出来，并且在最后输出的部分标出来，无需再进行查询。

### 🛠 Changes Overview

**Scope:** `packages/author_intel`, `packages/reporting`, `apps/analyzer`, `scripts/test_agent`, `docs`

**Key Actions:**

- **[Work-authorship only]**: Stage 4 不再按作者名搜索 OpenAlex / DBLP；作者画像只来自可信 OpenAlex work 的 `work.authorships.author.id`。
- **[Strict skip behavior]**: 论文身份不可信、无 selected work、无 authorship author id 时，直接跳过并记录原因，不再继续 name search。
- **[Author-id profiles]**: 可信 authorship author id 会通过 OpenAlex author-id 查询补 h-index、机构、领域等画像。
- **[Report visibility]**: `author_intel_skipped_papers` 写入 state、report.json、report.html 和 manual attention，报告新增“作者画像跳过说明”。
- **[Tests]**: Stage 4、Stage 7、runtime logging 和 E2E fixture 更新为 work-authorship-only contract。

### 🧠 Design Intent (Why)

旧 Stage 4 通过 `OpenAlex /authors?search=<name>` 取第一候选，重名作者容易错配，并进一步污染重要学者、机构分布和国家/地区地图。新策略选择“少查但不乱查”：只有论文身份和 authorship author id 足够可信时才生成作者画像。

### 📁 Files Modified

- `apps/analyzer/nodes.py`
- `packages/author_intel/models.py`
- `packages/author_intel/rules.py`
- `packages/author_intel/service.py`
- `packages/reporting/service.py`
- `packages/shared/models.py`
- `scripts/test_agent/e2e_mvp.py`
- `scripts/test_agent/runtime_logging_contract.py`
- `scripts/test_agent/stage4.py`
- `scripts/test_agent/stage7.py`
- `docs/ARCHITECTURE.md`
- `docs/QUALITY_SCORE.md`
- `docs/testing/stage-validation.md`
- `README.md`
- `.omx/plans/2026-05-19-stage4-work-authorship-author-intel.md`

### ✅ Verification

- `python scripts/test_agent/stage4.py`
- `python scripts/test_agent/stage7.py`
- `python scripts/test_agent/runtime_logging_contract.py`
- `python scripts/test_agent/e2e_mvp.py`
- `python scripts/test_agent/run.py --log detail`
