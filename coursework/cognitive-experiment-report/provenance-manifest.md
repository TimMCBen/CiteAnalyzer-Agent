# Provenance Manifest（当前非提交规划产物）

日期：2026-05-22

## 状态说明

当前 manifest 只追踪 pre-gate 规划产物，不追踪最终实验报告。后续一旦进入正式写作，需为每个报告章节、图、表、文献 claim 和数据 claim 增加独立行。

## 来源类型枚举

允许的 `source_type`：`real_data`、`approved_demo`、`literature`、`template`、`generated_prose`、`user_supplied`。

## 当前产物追踪

| artifact | claim_or_content | source_type | source_path_or_reference | allowed_use | disclosure_note |
| --- | --- | --- | --- | --- | --- |
| `integrity-decision-note.md` | 当前只能进入 policy-unknown / pre-gate 分支 | user_supplied | 用户说明为认知实验课大作业，但未提供题目/数据/rubric/政策 | 规划与风险控制 | 非提交稿，需人工确认课程政策 |
| `skill-audit.md` | 本地有 `humanizer-zh`，未发现 `humanizer-cn` | template | 本地 skill 列表与 `.codex/skills` 可用技能 | 工具选择 | 不能作为课程正文 |
| `skill-audit.md` | `blader/humanizer` 是英文 humanizer skill，可作表达层参考 | literature | https://github.com/blader/humanizer；https://agentskill.sh/%40blader/humanizer | 风格工具调研 | 不能用于规避 AI 检测 |
| `skill-audit.md` | `gmh5225/awesome-skills` 可作 Agent skills 索引 | literature | https://github.com/gmh5225/awesome-skills | 技能发现 | 需逐项核查 |
| `skill-audit.md` | `awesome-ai-research-writing-skill` 可作学术写作 skill 参考 | literature | https://github.com/zengrong233/awesome-ai-research-writing-skill | 工作流参考 | 不替代课程要求 |
| `outline-v1.md` | 标准认知实验报告章节结构 | template | `.omx/plans/prd-cognitive-experiment-report-workflow.md` | 非提交大纲 | 题目和 rubric 到位后需改写 |
| `outline-v1.md` | 图表计划依赖真实或获批 demo 数据 | template | `.omx/plans/test-spec-cognitive-experiment-report-workflow.md` | 图表规划 | 不生成结果图 |
| `provenance-manifest.md` | manifest 字段和分支红线 | template | `.omx/plans/test-spec-cognitive-experiment-report-workflow.md` | 追踪框架 | 后续正式稿需逐条扩展 |

## 待补来源

| future_item | 需要来源 | 当前状态 |
| --- | --- | --- |
| 实验题目/范式 | 用户或课程要求 | 待提供 |
| 被试信息 | 真实实验记录 | 待提供 |
| 原始数据 | 本地数据文件 | 待提供 |
| 文献引用 | DOI/论文/教材章节 | 待检索 |
| 统计结果 | 可复现分析脚本与输出 | 待数据到位 |
| 图表 | 源数据或流程依据 | 待生成 |
| AI 使用披露 | 课程政策 | 待确认 |

## 禁止占位

正式报告阶段不得出现未解析占位，如 `TODO`、`待补`、`[citation needed]`、虚假 DOI、虚构作者年份引用或无来源的统计值。当前 pre-gate 文件中的“待提供/待确认”只表示闸门状态，不是报告正文占位。
