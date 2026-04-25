# CiteAnalyzer-Agent

## 简介

`CiteAnalyzer-Agent` 是一个面向单篇目标论文的被引分析智能体项目。系统目标是输入一篇论文后，自动抓取施引文献，识别施引作者中的重点学者，分析引用语境与情感，并生成可视化分析报告。

当前项目已经完成阶段 1 和阶段 2 的主链路落地，正在从“架构与计划收口”转向“按阶段持续实现和联调”的状态。当前最稳定的能力是目标论文输入理解与施引文献抓取，后续重点将转向学者识别、引用情感分析和报告生成。

## 目标功能

- 施引文献抓取：围绕目标论文抓取施引文献元数据，并做多源融合与去重
- 学者识别：补充施引作者的 `h-index`、机构、领域信息，标注重量级学者候选
- 引用情感分析：提取引用上下文并判断是正向、中性还是批评性引用
- 可视化报告：生成引用趋势图、引用来源地图、学者分布和情感分布，并导出结构化结果与 HTML 报告

## 当前架构

当前系统采用“一个总智能体 + 多个子智能体”的总分架构：

- `论文被引分析智能体`：总控编排器，负责输入解析、流程调度、降级控制和最终结果汇总
- `文献爬取子智能体`：负责施引文献抓取、多源融合、去重与来源保留
- `学者识别子智能体`：负责作者画像补充、指标查询和重量级学者标注
- `引用情感分析子智能体`：负责引用上下文提取与情感分类
- `可视化报告子智能体`：负责汇总结果并生成 HTML 报告

```mermaid
flowchart LR
    paper_input["用户输入<br/>自然语言 / DOI / 标题 / 论文 ID / arXiv"]
    parse_stage["阶段 1<br/>输入理解与状态初始化"]
    fetch_stage["阶段 2<br/>施引文献抓取 / 补全 / 去重"]
    scholar_stage["阶段 4<br/>学者识别与影响力标注"]
    sentiment_stage["阶段 5<br/>引用上下文提取与情感分析"]
    report_stage["阶段 6<br/>汇总结果并生成 HTML 报告"]
    final_output["输出结果<br/>HTML 报告 + JSON"]

    paper_input --> parse_stage
    parse_stage --> fetch_stage
    fetch_stage --> scholar_stage
    fetch_stage --> sentiment_stage
    scholar_stage --> report_stage
    sentiment_stage --> report_stage
    report_stage --> final_output
```

更完整的说明见：

- [产品规格](docs/product-specs/citation-analysis-mvp.md)
- [架构文档](docs/ARCHITECTURE.md)
- [测试文档](docs/testing/README.md)

## 当前开发进度

已完成：

- 项目名称初始化
- MVP 产品规格初稿与规则收口
- 总智能体 + 子智能体架构文档
- 阶段 1：自然语言输入理解与状态初始化
- 阶段 2：`Semantic Scholar + Crossref` 主抓取链路
- 单篇真实 DOI 的阶段 2 在线样本验证
- 关键边界约定
  - `Semantic Scholar + Crossref` 为主抓取链路
  - `Google Scholar` 作为补充源，不阻塞主流程
  - `arXiv` 作为输入兼容入口
  - HTML 为当前默认报告输出方向
  - 重量级学者标注采用启发式规则

进行中：

- 阶段 4 之前的文档收口、边界细化和阶段联调准备

尚未开始：

- 学者识别模块实现
- 引用情感分析模块实现
- HTML 报告生成实现
- 端到端验证

## 仓库结构

- `docs/`：产品规格、架构、计划、历史记录
- `scripts/`：仓库级自动化脚本
- `downloaded-papers/`：本地下载论文和中间缓存
- `apps/` / `packages/` / `infra/`：后续实现阶段逐步落地

## 当前建议的下一步

1. 进入阶段 4，落地学者识别能力与作者画像补充。
2. 为阶段 5 明确全文入口、引用句子提取和情感分类边界。
3. 在更多真实 DOI 上补阶段 2 的在线回归验证。

## 许可证

[MIT](LICENSE)
