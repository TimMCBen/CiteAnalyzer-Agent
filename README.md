# CiteAnalyzer-Agent

## 简介

`CiteAnalyzer-Agent` 是一个面向单篇目标论文的被引分析智能体项目。系统目标是输入一篇论文后，自动抓取施引文献，识别施引作者中的重点学者，分析引用语境与情感，并生成可视化分析报告。

当前项目已经完成阶段 1 和阶段 2 的主链路落地，并在当前开发分支上推进到阶段 5 / 阶段 6 的原型实现。当前最稳定的能力是目标论文输入理解、施引文献抓取，以及面向真实论文全文的引用上下文定位实验路径。

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
    fulltext_stage["阶段 5<br/>全文抓取与文本解析"]
    sentiment_stage["阶段 6<br/>引用上下文提取与情感分析"]
    report_stage["阶段 7<br/>汇总结果并生成 HTML 报告"]
    final_output["输出结果<br/>HTML 报告 + JSON"]

    paper_input --> parse_stage
    parse_stage --> fetch_stage
    fetch_stage --> scholar_stage
    fetch_stage --> fulltext_stage
    fulltext_stage --> sentiment_stage
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
- 阶段 5 原型：`PDF-first` 全文抓取、本地落盘 `raw pdf/html + parsed txt`，不再把 tar 作为正式默认产物
- 阶段 6 原型：`LangGraph` 工作流、`PDF -> GROBID -> context` 主路径、GROBID 不可用时的文本回退路径、真实 `citing-5` 冒烟测试
- 关键边界约定
  - `Semantic Scholar + Crossref` 为主抓取链路
  - `Google Scholar` 作为补充源，不阻塞主流程
  - `arXiv` 作为输入兼容入口
  - HTML 为当前默认报告输出方向
  - 重量级学者标注采用启发式规则

进行中：

- 阶段 4 学者识别实现
- 阶段 6 多上下文返回与更多真实 citing paper 回归
- GROBID 路径向正式 stage6 主流程继续收口
- 阶段 5/6 的 PDF-first 契约继续向总智能体联调收口

尚未完成：

- 学者识别模块完整实现
- HTML 报告生成实现
- 多篇真实样本的端到端验证

## 仓库结构

- `docs/`：产品规格、架构、计划、历史记录
- `scripts/`：仓库级自动化脚本
- `downloaded-papers/`：本地下载论文和中间缓存
- `apps/` / `packages/` / `infra/`：后续实现阶段逐步落地

## 当前建议的下一步

1. 继续推进阶段 4，落地学者识别能力与作者画像补充。
2. 让阶段 6 对单篇 citing paper 返回多处引用上下文，而不是只保留一条主上下文。
3. 在更多真实 PDF 论文上补 GROBID 主路径回归，并为直接 LaTeX 来源保留兼容性验证。

## 许可证

[MIT](LICENSE)
