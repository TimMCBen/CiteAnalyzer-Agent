# CiteAnalyzer-Agent 框架组合参考

这份文档只整理当前项目在 `LangChain` 和 `LangGraph` 组合使用上可以直接参考的内容。

## 当前组合

- `LangGraph`：负责总智能体状态编排
- `LangChain`：负责模型调用、工具封装、结构化输出

## 当前项目里的可用点

### 总智能体

- `论文被引分析智能体`
  - 用 `LangGraph` 做总控状态图

### 子智能体

- `文献爬取智能体`
  - 作为可调用节点或工具能力
- `学者识别智能体`
  - 作为可调用节点或工具能力
- `引用情感分析智能体`
  - 作为可调用节点或工具能力
- `可视化报告智能体`
  - 作为最终输出节点

## 可直接参考的实现点

- 用 `StateGraph` 管总流程
- 用 `LangChain Tool` 封装外部 API
- 用 `LangChain` 接 LLM 做情感分析
- 用结构化输出生成统一状态对象
- 用 PromptTemplate / OutputParser 统一输入输出边界

## 当前项目可直接采用的对象与能力

- 总智能体编排：
  - `StateGraph`
  - `START`
  - `END`
- 模型接入：
  - `ChatOpenAI`
- Prompt：
  - `PromptTemplate`
  - `FewShotPromptTemplate`
- 输出解析：
  - `StrOutputParser`
  - `JsonOutputParser`
  - `PydanticOutputParser`
- 工具封装：
  - `tool`
  - LangChain Tools

## 当前约束

- 不改原始四个智能体名字
- 保留一个总智能体
- 用图状态推进，而不是只写固定顺序脚本
