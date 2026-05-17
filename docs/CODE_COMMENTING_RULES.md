# Python 用途注释规则

本规则用于 `apps/`、`packages/`、`scripts/` 下的 Python 代码。目标是让人和 Agent 能快速理解文件、类、函数的职责，而不是解释逐行实现。

## 总原则

- Python 源码 docstring 默认使用英文 ASCII。
- 注释只说明用途、职责、边界、输入输出意图或重要副作用。
- 不复述代码流程，不把函数名换一种说法，不写“sets value / returns result”这类低信息句子。
- 优先使用模块、类、函数 docstring，不新增零散行内注释。
- 不在注释中写真实 API key、本地绝对路径、真实日志片段或敏感信息。

## 覆盖矩阵

| 对象 | 默认规则 |
|---|---|
| 模块文件 | 必须有模块 docstring，说明文件职责。 |
| 非空 `__init__.py` | 写一句导出或包职责；空文件可豁免。 |
| 类 / dataclass / Protocol | 必须有类 docstring，说明领域角色、客户端职责或保存的状态。 |
| Protocol 方法 stub | 默认豁免，由 Protocol 类 docstring 表达契约。 |
| 公共顶层函数 | 必须有 docstring，说明稳定调用边界。 |
| 公共方法 | 必须有 docstring，除非是明显 accessor 或普通 dunder。 |
| 生产代码私有 helper | 非显然 helper 必须有 docstring；明显一行 helper 可豁免。 |
| `@property` / 明显 accessor | 默认豁免。 |
| 普通 dunder 方法 | 默认豁免。 |
| 嵌套局部函数 | 默认豁免；复杂时优先说明外层函数职责。 |
| `scripts/test_agent/assert_*` | 默认豁免，除非是复杂跨阶段 contract。 |
| 测试 fake/stub 类 | 必须有类 docstring，说明模拟哪个依赖。 |
| 测试 fake/stub 函数 | 默认豁免，复杂 fake 可补。 |

## 好例子

```python
"""Resolve a user paper query into target metadata used by later stages."""
```

```python
"""Client wrapper for retrieving normalized OpenAlex work candidates."""
```

```python
"""Build the report artifact from aggregated citation, author, and sentiment data."""
```

## 坏例子

```python
"""This function calls normalize, then loops through items, then returns rows."""
```

```python
"""Returns the result."""
```

```python
"""Class for AuthorProfile."""
```

## 执行要求

- 批量补注释前必须先运行 `scripts/test_agent/comment_contract.py --report-only` 了解缺口。
- 分批执行时使用 `--scope` 限定当前批次。
- 最终严格模式必须输出 `missing=0`。
- 每批改动后至少运行 `python -m compileall apps packages scripts` 和对应阶段测试。
