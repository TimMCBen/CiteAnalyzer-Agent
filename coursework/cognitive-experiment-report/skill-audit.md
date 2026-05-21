# 认知实验报告技能调研与适用性审计（研究用，非提交稿）

日期：2026-05-22

## 使用边界

本文件只用于选择后续工作流中的工具和技能，不是实验报告正文。由于课程 AI 政策未知，所有写作、润色、图表和统计能力都必须等 Gate 1-3 解决后才能用于可提交内容。

## 本地可用技能

| 技能 | 阶段 | 适用输入 | 预期输出 | 风险 | 当前结论 |
| --- | --- | --- | --- | --- | --- |
| `research-lookup` / `literature-review` | 文献检索 | 题目、关键词、理论框架 | 参考文献候选与背景摘要 | 可能引入不匹配文献 | 可用，但需人工/manifest 复核 |
| `statistical-analysis` | 数据分析 | 真实或获批 demo 数据 | 描述统计、推断统计建议 | 数据缺失时不能使用 | 数据到位后可用 |
| `academic-plotting` / `scientific-visualization` | 图表 | 已确认数据或流程结构 | 流程图、均值图、分布图、统计图 | 图像可能暗示不存在的结果 | 仅在数据/流程明确后使用 |
| `ppw:experiment` | 实验结果组织 | 设计、数据、统计输出 | 实验分析解读框架 | 容易越界写结论 | 只允许消费已验证统计结果 |
| `scientific-writing` | 学术写作 | 证据清单、结构大纲 | 规范化学术段落 | 政策未知时不能生成提交稿 | 目前只用于大纲规范 |
| `paper-polish-workflow` / `ppw:polish` | 学术润色 | 已锁定事实的草稿 | 更通顺的中文学术表达 | 可能改变论断强度 | 需 evaluator/editor 分离 |
| `humanizer-zh` | 中文表达润色 | 已审核草稿 | 减少模板化、口号式表达 | 不能用于规避检测或改事实 | 仅作表达层工具 |
| `ppw:de-ai` | 反模板化检查 | 已审核草稿 | AI 味风险提示与改写建议 | 学术诚信敏感 | 仅作可读性，不作规避检测 |
| `docx` / `pdf` | 导出 | 最终 Markdown 与图表 | DOCX/PDF | 格式可能偏离课程模板 | 输出格式明确后使用 |

本地未发现名为 `humanizer-cn` 的技能；可用的中文方向技能是 `humanizer-zh`。

## 在线资源核查

| 资源 | 类型 | 相关性 | 可用方式 | 风险判断 |
| --- | --- | --- | --- | --- |
| `gmh5225/awesome-skills`：https://github.com/gmh5225/awesome-skills | Agent skills 索引 | 用于发现跨平台 skills | 只作目录，不直接采信 | 需要逐个核查来源与维护状态 |
| `blader/humanizer`：https://github.com/blader/humanizer | 英文 humanizer skill | 可借鉴 evaluator/editor 结构 | 不直接用于中文报告 | 易被误用为 AI 检测规避 |
| agentskill.sh `@blader/humanizer`：https://agentskill.sh/%40blader/humanizer | skill 分发页 | 提供 Codex 安装路径说明 | 仅作安装/元数据参考 | 仍需读原始 `SKILL.md` |
| `zengrong233/awesome-ai-research-writing-skill`：https://github.com/zengrong233/awesome-ai-research-writing-skill | Codex 学术写作 skill 包 | 涵盖翻译、润色、审稿、图示 | 可作为 prompt/工作流参考 | 不应直接替代课程要求 |
| `Leey21/awesome-ai-research-writing` 相关索引 | 学术写作 prompt/资源集合 | 可辅助找写作和审稿模板 | 需核查上游链接 | 维护状态和质量不一 |
| `hvpandya.com/stop-slop` / Stop Slop | 反模板化写作清理 | 可借鉴减少空泛表达 | 只作风格检查 | 不能改变事实、数据或结论 |

## 推荐工具链

### 当前 pre-gate 阶段

1. `research-lookup` / web research：只用于技能和资料来源调研。
2. `scientific-writing`：只用于标准报告结构，不写可提交正文。
3. `provenance-manifest` 手工维护：记录每个规划产物的来源和用途。

### Gate 解决后的完整报告阶段

1. 文献：`literature-review` + `research-lookup`，由 verifier 检查引用。
2. 统计：`statistical-analysis`，只处理真实或明确获批 demo 数据。
3. 图表：`academic-plotting` / `scientific-visualization`，每图必须有源数据或流程依据。
4. 写作：`scientific-writing` / writer lanes，按章节分工。
5. 润色：`humanizer-zh` + evaluator/editor 分离循环，最多三轮，仅改表达。
6. 导出：`docx` / `pdf`，仅在最终格式明确后使用。

## 红线

- 不用 humanizer 类技能隐藏 AI 参与。
- 不用任何 skill 生成虚假实验数据、统计结果、参考文献或课程要求。
- 不把英文 humanizer 结果直接套到中文学术报告。
- 润色不得改变假设、方法、统计值、引用、结论、立场或证据强度。
