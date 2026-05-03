# MVP 收口执行计划：未完成任务分阶段 / 分分支推进

## 目标

把当前仓库从“阶段 1 / 2 已完成、阶段 5 / 6 有原型、阶段 4 / 7 缺失、总控未闭环”的状态，推进到可验证的 MVP 闭环：

- `apps/analyzer` 总控可调度阶段 `1 / 2 / 4 / 5 / 6 / 7`
- `stage7.py` 只承担报告级 contract 验证
- `scripts/test_agent/e2e_mvp.py` 负责真实样本总控验证
- 仓库文档、测试入口、质量结论与真实能力一致
- 最终保留提交都具备可审计的智能体验证 gate

## 范围

- 包含：
  - baseline 文档与验证基线收口
  - 阶段 4 学者识别实现
  - 阶段 5 / 6 接回 analyzer 总控
  - 阶段 7 报告生成
  - 独立 E2E 验证入口
  - history / quality / docs 同步
- 不包含：
  - `Google Scholar` 默认接入主链路
  - 阶段 6 多上下文返回
  - Web UI
  - PDF 首版正式交付
  - 训练式高精度情感分类

## 背景

- 相关文档：
  - `README.md`
  - `docs/ARCHITECTURE.md`
  - `docs/testing/stage-validation.md`
  - `docs/QUALITY_SCORE.md`
  - `docs/product-specs/citation-analysis-mvp.md`
  - `docs/exec-plans/active/2026-04-24-citation-analysis-mvp.md`
  - `docs/exec-plans/active/2026-04-26-stage3-google-scholar-supplement.md`
  - `docs/exec-plans/active/2026-04-26-stage4-scholar-intel-agent.md`
  - `docs/exec-plans/active/2026-04-26-stage5-citation-sentiment-agent.md`
- 相关代码路径：
  - `apps/analyzer/`
  - `packages/shared/`
  - `packages/sentiment/`
  - `packages/citation_sources/`
  - `packages/author_intel/`（待实现）
  - `packages/reporting/`（待实现）
  - `scripts/test_agent/`
- 已知约束：
  - `Google Scholar` 当前仅保留调试 / 人工核查定位，不进入首轮默认实现
  - 报告层不直接调用外部学术 API
  - 复杂任务需要维护 active execution plan
  - 行为变化需同轮同步文档
  - 每次最终保留提交都要设置一个智能体核实开发程度

## 本轮冻结决策

### 提交审计规则

采用“分支内允许中间 commit，但合并前必须收敛为带 verifier gate 的最终保留 commits”。

- 开发分支内部允许中间 commit。
- 合并前必须 `squash` / `rebase` 成一组最终保留 commits。
- 每个最终保留 commit 都必须有：
  - 唯一明确的功能边界
  - 一个 verifier 角色
  - 一组检查命令或检查点
  - 可追溯的通过依据
- 审计对象是最终保留在历史中的 commits，不是临时提交。

### Stage 6 契约冻结

本轮 MVP 明确冻结为：

- 每篇 citing paper 仅返回一条主 `CitationContext`
- `CitationContext` 可以是 `unknown`
- `SentimentSummary` 按单上下文聚合
- 本轮不得为多上下文改动 `stage7` 输入契约

多上下文返回延期到 MVP 闭环完成后另开计划。

### Stage 7 / E2E 边界冻结

- `scripts/test_agent/stage7.py` 只做报告级 contract / fixture 验证
- `scripts/test_agent/e2e_mvp.py` 只做真实样本总控验证
- `stage7.py` 的 fixture 来源固定为本地构造或落盘的 analyzer 状态夹具，不依赖外部 live 请求

## RALPLAN-DR 摘要

### Principles

1. 先补闭环，再补 recall / 精度增强。
2. 以当前代码和可运行脚本为真实基线，不以过期计划文字为准。
3. 总控集成优先收口已有稳定 contract，不在闭环前引入新的状态维度。
4. 阶段 contract 验证与真实样本 E2E 验证分层。
5. 审计对象是最终保留 commit，不是分支里的临时历史。

### Decision Drivers

1. 当前真实阻塞项是阶段 4、阶段 7、analyzer 集成、E2E 联调。
2. 当前 stage6 代码和脚本都体现“单上下文主契约”，多上下文不是本轮最短路径。
3. baseline 文档同步仍不完整，`README/testing/run.py` 之外还必须同步 `ARCHITECTURE` 与 `product-specs`。
4. stage7 与 E2E 目前职责混杂，必须机械拆层。
5. 用户要求每次提交具备智能体核实程度，需要变成可审计规则。

### Viable Options

#### 方案 A：先补 stage4，再接回 stage5/6，再做 stage7，最后独立 E2E

- 优点：依赖顺、返工最小、最利于 verifier gate 审计
- 缺点：最终 HTML 结果出现稍晚

#### 方案 B：先做 stage7 骨架，再倒逼上游

- 优点：更早看到最终产物
- 缺点：上游 state / report input contract 不稳，返工高

#### 方案 C：先接回 stage5/6，再补 stage4 和 stage7

- 优点：更早暴露总控 state 缺口
- 缺点：主闭环仍缺 author-intel，易按 sentiment 方向先塑形后返工

### 决策

采用方案 A，并附加三项硬冻结：

- stage6 本轮维持单上下文
- stage7 与 E2E 明确拆层
- analyzer 集成分支只负责编排接线与状态 glue，不吸收 domain logic

## 风险

- 风险：stage6 在集成分支被顺手扩成多上下文
  - 缓解方式：本计划明确冻结为单上下文；多上下文必须另开计划
- 风险：stage7 和 E2E 再次混到同一个脚本
  - 缓解方式：`stage7.py` 与 `e2e_mvp.py` 分别命名并固定职责
- 风险：baseline 只改 README/testing/run.py，遗漏架构与产品规格
  - 缓解方式：把 `docs/ARCHITECTURE.md` 与 `docs/product-specs/citation-analysis-mvp.md` 列为 baseline 必改文件
- 风险：analyzer 集成分支职责扩散
  - 缓解方式：只允许修改 `apps/analyzer/*` 与 `packages/shared/models.py` 做编排 / glue；逐篇调度循环写在 `nodes.py` 视为允许的 glue，不算 domain logic 下沉
- 风险：`run.py` 收口责任不清
  - 缓解方式：baseline 分支只修正其现状说明；最终把它升级成正式聚合入口的责任归到 E2E 分支

## 分支执行表

| branch | owned files | blocked by | branch-end commands | verifier role | pass assertions |
| --- | --- | --- | --- | --- | --- |
| `docs/refresh-mvp-baseline` | `README.md`, `docs/testing/stage-validation.md`, `scripts/test_agent/run.py`, `docs/ARCHITECTURE.md`, `docs/product-specs/citation-analysis-mvp.md`, `docs/exec-plans/active/2026-04-24-citation-analysis-mvp.md`, 本文件 | 无 | `python scripts/test_agent/run.py` | `verifier` | 文档与脚本一致声明 `stage5=fulltext`, `stage6=context+sentiment`, `stage7=reporting`；`run.py` 仍只把 `3/4/7` 标为 pending；`stage7.py` 与 `e2e_mvp.py` 的边界已写清 |
| `feat/stage4-author-intel` | `packages/author_intel/**`, `packages/shared/models.py`, `scripts/test_agent/stage4.py` | baseline | `python scripts/test_agent/stage4.py`; `python scripts/test_agent/run.py` | `test-engineer` | 能输出 `AuthorProfile` / `ScholarLabel`；覆盖高影响力、重量级、弱标注 / 证据不足；无法稳定匹配作者时不强行高置信合并 |
| `feat/stage56-analyzer-integration` | `apps/analyzer/nodes.py`, `apps/analyzer/graph.py`, `apps/analyzer/main.py`, `packages/shared/models.py`；必要时最小化调整 `scripts/test_agent/run.py` | baseline, stage4 contract | `python scripts/test_agent/stage5.py`; `python scripts/test_agent/stage6.py`; `python scripts/test_agent/run.py` | `verifier` | analyzer 可调度 stage4/5/6；`nodes.py` 允许逐篇调度循环作为 glue；`main.py` 暴露统一分析入口；stage5 失败、stage6 unknown、GROBID 不可用时总控可继续推进 |
| `feat/stage7-reporting` | `packages/reporting/**`, `packages/shared/models.py`, `apps/analyzer/nodes.py`, `apps/analyzer/graph.py`, `scripts/test_agent/stage7.py`, `scripts/test_agent/fixtures/reporting/**` | stage4, stage56 integration | `python scripts/test_agent/stage7.py` | `verifier` | `stage7.py` 只验证报告 contract / fixture；HTML/JSON 产物存在；包含目标论文基础信息、趋势、来源、学者、情感、降级说明；不回调外部学术 API |
| `feat/e2e-real-sample-validation` | `scripts/test_agent/e2e_mvp.py`, `scripts/test_agent/run.py`, `README.md`, `docs/testing/stage-validation.md`, `docs/ARCHITECTURE.md`, `docs/product-specs/citation-analysis-mvp.md`, `docs/QUALITY_SCORE.md`, `docs/histories/**` | stage7 | `python scripts/test_agent/stage1.py`; `python scripts/test_agent/stage2.py`; `python scripts/test_agent/stage4.py`; `python scripts/test_agent/stage5.py`; `python scripts/test_agent/stage6.py`; `python scripts/test_agent/stage7.py`; `python scripts/test_agent/e2e_mvp.py`; `python scripts/test_agent/run.py` | `verifier` | 真实样本跑通 `1/2/4/5/6/7`；报告生成成功；局部失败可降级暴露；`run.py` 升级为最终聚合入口并调用 `stage4.py`、`stage7.py`，对 `e2e_mvp.py` 给出显式入口或可选执行说明 |

## 分阶段推进

### Stage 0：Baseline 基线收口

- 目标：
  - 同步 active plan、README、testing、architecture、product spec 的当前真相
  - 把 `stage6` 单上下文、`stage7` 报告级验证、`e2e_mvp.py` 独立入口写成正式口径
- 最终保留 commit 建议：
  - `docs: refresh active MVP contract baseline`
  - `docs: sync architecture product spec and stage validation entrypoints`
- 智体验证：
  - 第 1 个最终 commit：`code-reviewer`
    - 核对 active plan 与当前 repo 真相是否一致
  - 第 2 个最终 commit：`verifier`
    - 核对 README / testing / architecture / product-spec 是否无冲突

### Stage 1：阶段 4 学者识别主链路

- 目标：
  - 实现 `AuthorProfile` / `ScholarLabel`
  - 以 `OpenAlex` 为主、`DBLP` 为辅完成弱画像与标注
- 验收矩阵至少覆盖：
  - `h-index >= 30` 且频次 >= 2
  - 只有 `h-index >= 30`
  - 缺 `h-index` 但有频次 / 机构信息，输出弱标注与证据不足
  - 无法稳定匹配时不高置信合并
- 最终保留 commit 建议：
  - `feat: add author-intel models and enrichment contract`
  - `feat: implement scholar enrichment and labeling validation`
- 智体验证：
  - 第 1 个最终 commit：`code-reviewer`
    - 看模型边界、来源职责、弱画像策略
  - 第 2 个最终 commit：`test-engineer`
    - 看 `stage4.py` 是否覆盖最小验收矩阵

### Stage 2：Stage5/6 接回 analyzer 总控

- 目标：
  - 让 `run_analysis()` 不再停在 stage2
  - 把 stage4 / stage5 / stage6 的状态写回 analyzer 总控
- 允许的 glue：
  - 在 `apps/analyzer/nodes.py` 中做逐篇 fulltext / sentiment 调度循环
  - 在 `packages/shared/models.py` 中补 analyzer 需要的共享状态字段
- 禁止的扩 scope：
  - 不在本分支重写 sentiment 领域逻辑
  - 不在本分支切换为多上下文
- analyzer -> reporting 冻结输入字段至少应包含：
  - `target_paper`
  - `citing_papers`
  - `fetch_summary`
  - `source_trace`
  - `author_profiles`
  - `scholar_labels`
  - `author_summary` 或等价聚合统计
  - `citation_contexts`
  - `sentiment_summary`
- 最终保留 commit 建议：
  - `feat: extend analyzer state for scholar fulltext and sentiment outputs`
  - `feat: wire stage4 stage5 and stage6 into analyzer graph`
- 智体验证：
  - 第 1 个最终 commit：`code-reviewer`
    - 看 state glue 是否最小、是否误吸收 domain logic
  - 第 2 个最终 commit：`verifier`
    - 看总控顺序、降级路径、统一入口是否成立

### Stage 3：Stage7 报告生成

- 目标：
  - 实现 `packages/reporting/`
  - 生成 HTML + JSON 报告
  - 固定 `stage7.py` 为报告 contract / fixture 验证
- `stage7.py` fixture 来源：
  - 优先使用本地构造或落盘的 analyzer 状态夹具
  - 不依赖真实外部 live 请求
- 报告最低断言：
  - HTML / JSON 都生成
  - 包含目标论文基础信息
  - 包含年份趋势、来源地图、学者分布 / 代表作者、情感分布
  - 包含结论与人工关注项
  - 显式暴露降级 / 缺失数据
- 最终保留 commit 建议：
  - `feat: add report artifact contract and renderer`
  - `feat: integrate reporting node and add stage7 contract validation`
- 智体验证：
  - 第 1 个最终 commit：`code-reviewer`
    - 看报告输入契约是否只消费上游状态
  - 第 2 个最终 commit：`verifier`
    - 看报告产物、降级说明、fixture 验证是否成立

### Stage 4：独立 E2E 联调与收尾

- 目标：
  - 用真实样本验证完整 analyzer 闭环
  - 升级 `run.py` 为最终聚合入口
  - 同步 README / testing / architecture / product-spec / quality / history
- `run.py` 最终收口规则：
  - 本分支负责把 `run.py` 升级为正式聚合入口
  - `run.py` 至少直接执行 `stage1.py`, `stage2.py`, `stage4.py`, `stage5.py`, `stage6.py`, `stage7.py`
  - `run.py` 对 `e2e_mvp.py` 给出显式入口：可以直接调用，或清楚打印“单独运行此命令完成真实样本 E2E”
- E2E 必测降级路径：
  - 全文缺失
  - GROBID 不可用
  - 作者指标不完整
  - 报告仍可生成且显式标记影响
- 最终保留 commit 建议：
  - `test: add real-sample end-to-end analyzer validation`
  - `docs: sync architecture product spec quality and history after MVP closure`
- 智体验证：
  - 第 1 个最终 commit：`verifier`
    - 看真实样本总控路径与降级路径
  - 第 2 个最终 commit：`code-reviewer`
    - 看文档、质量评分、history 是否与真实结果一致

## 验证方式

- 命令：
  - `python scripts/test_agent/stage1.py`
  - `python scripts/test_agent/stage2.py`
  - `python scripts/test_agent/stage4.py`
  - `python scripts/test_agent/stage5.py`
  - `python scripts/test_agent/stage6.py`
  - `python scripts/test_agent/stage7.py`
  - `python scripts/test_agent/e2e_mvp.py`
  - `python scripts/test_agent/run.py`
- 手工检查：
  - analyzer 主入口能串起 `1/2/4/5/6/7`
  - stage7 只做报告级验证，不承担真实样本总控
  - 报告能显式暴露降级信息
  - 最终保留 commits 均具备 verifier gate
- 观测检查：
  - 记录去重前后文献数量
  - 记录作者画像成功数量与标签分布
  - 记录 sentiment 成功 / unknown / 失败数量
  - 记录报告导出路径
  - 记录总控节点顺序与降级决策

## 进度记录

- [x] 梳理当前未完成主线与暂缓项
- [x] 冻结 stage6 单上下文契约
- [x] 冻结 stage7 / E2E 验证边界
- [x] 明确分支切分、owned files、verifier gate
- [ ] baseline 分支落库并同步 canonical docs
- [ ] 实现 stage4 author-intel
- [ ] 接回 stage4/5/6 到 analyzer 总控
- [ ] 实现 stage7 reporting
- [ ] 实现 `scripts/test_agent/e2e_mvp.py`
- [ ] 完成真实样本 E2E 与文档收尾

## 决策记录

- 2026-05-04：当前 MVP 不把 `Google Scholar` 升级为默认实现，继续保持补充源定位。
- 2026-05-04：stage6 本轮冻结为单上下文 contract，多上下文延期到 MVP 闭环之后。
- 2026-05-04：`stage7.py` 与 `e2e_mvp.py` 明确拆层，前者负责报告 contract，后者负责真实样本总控验证。
- 2026-05-04：每次最终保留提交都必须配置 verifier gate；开发过程中的临时提交不作为最终审计证据。
