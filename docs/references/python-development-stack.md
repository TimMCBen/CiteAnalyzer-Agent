# Python 开发栈参考

这份文档整理的是适合 `CiteAnalyzer-Agent` 当前 MVP 阶段采用的一组 Python 开发现成方案。这里不追求罗列所有可能工具，而是沉淀后续实现中最可能反复参考的组合与外部资料入口。

当前推荐组合是：

- `Ruff`：统一承担 lint 与格式化
- `dataclasses`：作为内部核心数据对象的默认表达方式
- `Pydantic`：作为边界输入输出与配置校验工具
- `pyproject.toml`：作为 Python 项目配置的统一入口

## 选择原则

当前阶段采用这套组合，主要基于以下考虑：

- 先建立轻量稳定的工程基线，而不是一次性引入过重约束
- 优先保证双人协作时的数据结构和代码风格一致
- 让内部对象和外部边界使用不同强度的约束方式
- 为后续扩展留空间，但不提前堆叠复杂工具链

## Ruff

### Ruff 的适用场景

`Ruff` 适合作为当前项目的统一代码质量工具，原因是它可以同时承担：

- 基础 lint
- 代码格式化

这对 MVP 阶段尤其合适，因为不需要同时维护 `black`、`isort`、`flake8` 等多套配置。

### Ruff 的项目建议

- 默认使用 `ruff check`
- 默认使用 `ruff format`
- 在首轮实现阶段，不建议并行引入更多风格工具

### Ruff 参考链接

- Ruff 文档首页：<https://docs.astral.sh/ruff/>
- Ruff Linter：<https://docs.astral.sh/ruff/linter/>
- Ruff Formatter：<https://docs.astral.sh/ruff/formatter/>

## dataclasses

### dataclasses 的适用场景

`dataclasses` 适合作为内部标准对象的默认表达方式。对于当前项目中这类对象：

- `TargetPaper`
- `CitingPaper`
- `AuthorProfile`
- `ScholarLabel`
- `CitationContext`

使用 `dataclass` 有几个明显好处：

- 标准库自带
- 结构清晰
- 适合子智能体之间传递标准化对象

### dataclasses 的项目建议

- 内部核心对象优先使用 `dataclass`
- 不要在首轮实现里大量直接传递原始 `dict`
- 如果后续边界校验需求上升，再把部分边界对象切换到 `Pydantic`

### dataclasses 参考链接

- Python `dataclasses` 官方文档：<https://docs.python.org/3/library/dataclasses.html>

## Pydantic

### Pydantic 的适用场景

`Pydantic` 更适合作为边界层工具，而不是在第一阶段替代所有内部对象。它适合处理：

- 外部 API 响应校验
- 配置对象
- 报告导出结构
- 需要更强合法性校验的输入输出模型

### Pydantic 的项目建议

- 第一阶段不要求所有内部对象都使用 `Pydantic`
- 优先用于配置和边界模型
- 在外部数据源接入增多后，再逐步增加使用范围

### Pydantic 参考链接

- Pydantic Models：<https://docs.pydantic.dev/latest/concepts/models/>
- Pydantic Dataclasses：<https://docs.pydantic.dev/latest/concepts/dataclasses/>

## pyproject.toml

### pyproject.toml 的适用场景

`pyproject.toml` 是当前 Python 项目的统一配置入口，适合承载：

- 项目元数据
- 工具配置
- 格式化与 lint 规则
- 后续依赖管理入口

### pyproject.toml 的项目建议

- Python 代码骨架落地时优先补齐 `pyproject.toml`
- 将 `Ruff` 和后续 Python 工具配置统一收敛到这里
- 不建议在 MVP 阶段把工具配置分散到多个独立文件

### pyproject.toml 参考链接

- Python Packaging User Guide：<https://packaging.python.org/en/latest/>
- Declaring project metadata：<https://packaging.python.org/specifications/declaring-project-metadata/>

## 对当前项目的落地顺序建议

### 第一阶段

- 建立 `pyproject.toml`
- 接入 `ruff check`
- 接入 `ruff format`
- 用 `dataclass` 定义核心对象

### 第二阶段

- 在外部 API 边界上逐步引入 `Pydantic`
- 对配置对象和外部响应做更明确校验

### 第三阶段

- 再根据实现复杂度决定是否增加更严格的类型检查或测试约束

## 当前不建议立即做的事

以下做法不建议在 MVP 第一阶段就引入：

- 同时引入 `black`、`isort`、`flake8`、`pylint` 等多套工具
- 一开始就对全仓库启用严格 `mypy`
- 一开始就把所有对象都切换成 `Pydantic`
- 为尚未实现的模块预先堆叠过多工程配置

## 本项目当前结论

当前阶段最适合的 Python 开发基线是：

- `Ruff` 负责代码规范
- `dataclass` 负责内部核心对象
- `Pydantic` 负责边界校验
- `pyproject.toml` 负责统一配置

这套组合足以支持当前 MVP 落地，同时保留后续扩展空间。
