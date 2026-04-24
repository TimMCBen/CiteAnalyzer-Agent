# LangGraph 参考

这份文档只整理 `LangGraph` 在当前项目中值得长期保留的参考点。

## 适合参考的内容

- StateGraph 状态图
- 节点与边
- 条件跳转
- 状态持有
- 失败 / 降级路径设计

## 当前项目里的可用点

- 作为 `论文被引分析智能体` 的总控状态图
- 编排以下子智能体：
  - `文献爬取智能体`
  - `学者识别智能体`
  - `引用情感分析智能体`
  - `可视化报告智能体`
- 控制抓取、识别、分析、报告生成的状态推进
- 处理失败后继续输出部分结果

## 当前项目优先可用的 LangGraph 能力

- `StateGraph`
- 节点定义
- 边定义
- 条件跳转
- 状态对象传递
- 降级路径设计

## 可以重点查看的类与能力

- 图结构：
  - `StateGraph`
- 流程边界：
  - `START`
  - `END`
- 核心能力：
  - 节点定义
  - 边定义
  - 条件跳转
  - 状态对象传递
  - 工作流与 agent 组织方式

## 官方链接

- LangGraph Overview：<https://docs.langchain.com/oss/python/langgraph/overview>
- LangGraph Workflows and agents：<https://docs.langchain.com/oss/python/langgraph/workflows-agents>
- LangGraph Thinking in LangGraph：<https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph>
