# LangChain 参考

这份文档只整理 `LangChain` 在当前项目中值得长期保留的参考点。

## 适合参考的内容

- 模型调用统一接口
- Prompt 模板
- 输出解析
- Tool 封装
- 结构化输出

## 当前项目里的可用点

- 给引用情感分析智能体接入 LLM
- 把外部能力封装成工具
  - `Semantic Scholar`
  - `Crossref`
  - `OpenAlex`
- 文本提取
- 报告生成
- 统一 prompt 和结构化输出格式

## 当前项目优先可用的 LangChain 组件

- `ChatOpenAI`
- `PromptTemplate`
- `FewShotPromptTemplate`
- `StrOutputParser`
- `JsonOutputParser`
- `PydanticOutputParser`
- `tool` / Tool 封装
- 结构化输出能力

## 可以重点查看的类与能力

- 模型接入：
  - `ChatOpenAI`
- Prompt：
  - `PromptTemplate`
  - `FewShotPromptTemplate`
- 输出解析：
  - `StrOutputParser`
  - `JsonOutputParser`
  - `PydanticOutputParser`
- 工具：
  - `tool`
  - LangChain Tools
- 结构化输出：
  - structured output

## 官方链接

- LangChain Overview：<https://docs.langchain.com/oss/python/langchain/overview>
- LangChain Agents：<https://docs.langchain.com/oss/python/langchain/agents>
- LangChain Tools：<https://docs.langchain.com/oss/python/langchain/tools>
- LangChain Structured output：<https://docs.langchain.com/oss/python/langchain/structured-output>
