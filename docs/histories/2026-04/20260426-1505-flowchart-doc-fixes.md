# 本次诉求

用户希望我检查当前仓库里的流程图问题，并直接改一版文档里的图，方便对比效果。

## 主要改动

- 调整阶段 1 流程图，把原本过粗的 `uncertain` 状态拆成 `ambiguous` 和 `insufficient`。
- 调整 `docs/ARCHITECTURE.md` 的总览图，把调度关系和关键中间产物一起表达出来，避免只剩“主智能体来回调用子智能体”的抽象画法。
- 调整阶段 2 流程图，补上目标论文解析失败、主链路零结果、Crossref 补充失败但仍继续输出的降级分支。
- 调整阶段 3 标题和输出节点文案，明确这是一张接入决策图，不是运行时流程图。
- 调整阶段 4 流程图，把 `DBLP` 从必经节点改成按需辅助校验路径，并加入弱画像降级表达。
- 调整阶段 5 流程图，区分“无全文”“未定位到引用”“上下文不足”三类失败路径。

## 设计动机

原来的图大多过于线性，和文档反复强调的 Agent 编排、局部失败、降级交付、显式产物边界并不完全一致。此次修改的目标不是把图画复杂，而是让图能更直接约束后续实现和测试。

## 关键受影响文件

- `docs/ARCHITECTURE.md`
- `docs/exec-plans/active/2026-04-24-citation-analysis-mvp.md`
- `docs/exec-plans/active/2026-04-25-stage2-citation-fetch-agent.md`
- `docs/exec-plans/active/2026-04-26-stage3-google-scholar-supplement.md`
- `docs/exec-plans/active/2026-04-26-stage4-scholar-intel-agent.md`
- `docs/exec-plans/active/2026-04-26-stage5-citation-sentiment-agent.md`
