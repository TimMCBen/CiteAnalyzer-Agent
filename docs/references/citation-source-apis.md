# Citation Source API 参考

这份文档整理 `CiteAnalyzer-Agent` 阶段 2 当前最相关的两个外部学术数据源：

- `Semantic Scholar API`
- `Crossref REST API`

目标不是复制官方文档，而是回答当前项目真正需要的三个问题：

1. 这些 API 是否免费
2. 有哪些现成调用方式
3. 对阶段 2 最适合的接入方式是什么

## 结论先看

- `Semantic Scholar`
  - 适合作为阶段 2 的**主 citation source**
  - 适合负责目标论文解析和施引文献主抓取
- `Crossref`
  - 适合作为阶段 2 的**metadata enrichment source**
  - 适合补 DOI、标题、venue、年份等元数据
  - 不适合作为和 `Semantic Scholar` 对等的施引主来源

## 1. 是否免费

### Semantic Scholar API

- 官方公开提供
- 基础使用免费
- 推荐使用 API key
- 带 key 可获得稳定身份识别与更明确的配额

当前官方教程说明中，个人 API key 默认是**全接口合计 1 request/second**。

对当前项目的意义：

- MVP 阶段可以免费接入
- 但必须控制请求频率，不适合一开始就做高并发抓取

官方入口：

- `https://www.semanticscholar.org/product/api`
- `https://www.semanticscholar.org/product/api/tutorial`

### Crossref REST API

- 官方公开提供
- 免费使用
- 不要求注册
- 官方推荐通过 `mailto` 进入 polite pool，获得更友好的服务质量

对当前项目的意义：

- MVP 阶段可直接免费使用
- 适合做补全、校验和低频查询
- 不应假设它能免费稳定提供完整 citing works 列表

官方入口：

- `https://www.crossref.org/documentation/retrieve-metadata/rest-api/`
- `https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/`
- `https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/`

## 2. 现成调用方式

### Semantic Scholar

当前可选调用方式：

- 官方 REST API
- 官方 Postman Collection
- 社区 Python client

#### 官方 REST API

最值得直接参考的能力：

- `paper/{paper_id}`
- `paper/{paper_id}/citations`
- `paper/search/match`

当前项目最可能用到：

- 用 DOI / paper id / 标题先定位目标论文
- 再获取目标论文的施引记录

#### 官方 Postman

适合：

- 调接口前先手工试字段
- 快速验证返回结构

#### 社区 Python client

目前常见的是社区维护库，不是官方 SDK：

- PyPI：`semantic-scholar-api`
- GitHub：`danielnsilva/semanticscholar`

适合：

- 快速探索接口能力

不建议：

- 直接把社区库作为阶段 2 的核心依赖边界

#### 第三方代理平台

如果官方 API 在当前网络环境下握手不稳定，或者默认速率限制影响阶段验证，也可以接入第三方代理平台。

当前项目已经记录过一个可选方案：

- 代理地址：`https://s2api.ominiai.cn/s2`
- 接入方式：
  - 将官方域名 `https://api.semanticscholar.org` 替换为 `https://s2api.ominiai.cn/s2`
  - 将 `x-api-key` 鉴权改为 `Authorization: Bearer <token>`

对当前项目的落地方式：

- `SEMANTIC_SCHOLAR_BASE_URL`
- `SEMANTIC_SCHOLAR_API_KEY`
- `SEMANTIC_SCHOLAR_AUTH_MODE=bearer`

风险边界：

- 这是第三方代理，不是 `Semantic Scholar` 官方服务
- 项目应把它视为“可选网络接入层”，不要在架构文档中把它等同于官方能力边界
- token 只能保存在本地 `.env` 或安全的 secret store 中，不能写进仓库

### Crossref

当前可选调用方式：

- 官方 REST API
- 社区 Python client

#### 官方 REST API

最值得直接参考的能力：

- `works/{doi}`
- `works?query.bibliographic=...`
- `select`
- `rows`
- `cursor`

当前项目最可能用到：

- 通过 DOI 拉单篇元数据
- 用标题 / 年份 / 作者做候选匹配
- 补 DOI、venue、年份、引用计数等字段

#### 社区 Python client

常见的是社区维护库：

- GitHub：`fabiobatalha/crossrefapi`

适合：

- 快速原型

不建议：

- 把整个阶段 2 的 Crossref 能力建立在社区库的内部抽象上

## 3. 为什么 `Crossref` 不适合作为主 citation source

这是阶段 2 最重要的边界判断。

原因不是“Crossref 不好”，而是它的官方能力边界决定了：

- 公开 REST API 更适合做元数据检索和补全
- 完整 citing DOI 列表属于 `Cited-by` 能力
- `Cited-by` 不是普通公共 REST 用法下就能当成主抓取链路来依赖的能力

也就是说：

- `Semantic Scholar` 更像 citation graph source
- `Crossref` 更像 metadata source

如果把两者都当成“施引列表主来源”，服务边界会变得混乱，后面调试时也很难判断到底哪条链路负责召回、哪条链路负责补全。

官方参考：

- `https://www.crossref.org/documentation/cited-by/`
- `https://www.crossref.org/documentation//cited-by/retrieve-citations/`

## 4. 对阶段 2 的推荐接入方式

### 推荐角色分工

`SemanticScholarClient`

- 负责目标论文解析
- 负责主施引文献抓取
- 负责 citation graph 语义

`CrossrefClient`

- 负责 DOI 元数据补全
- 负责标题 / 书目信息匹配
- 负责 citation count 或补充字段校验

### 推荐调用顺序

1. 先用 `Semantic Scholar` 定位目标论文
2. 用 `Semantic Scholar` 拉主施引候选
3. 对候选记录做标准化
4. 再用 `Crossref` 对缺 DOI / 元数据弱的记录做补全
5. 最后统一去重和来源追踪

### 推荐接口边界

建议当前项目内部采用薄客户端，而不是直接暴露第三方库对象：

```python
class SemanticScholarClient:
    def resolve_target_paper(self, target_paper: TargetPaper) -> dict: ...
    def fetch_citations(self, paper_id: str, max_results: int = 100) -> list[dict]: ...


class CrossrefClient:
    def fetch_work_by_doi(self, doi: str) -> dict | None: ...
    def search_work_match(
        self,
        title: str,
        year: int | None = None,
        authors: list[str] | None = None,
    ) -> dict | None: ...
```

这样做的好处：

- 项目自己的服务层只依赖稳定的内部契约
- 后续即使换成别的 SDK 或直接换 HTTP 实现，也不用把改动扩散到整个状态图和测试层

## 5. 阶段 2 当前最适合先做什么

建议顺序：

1. 先实现 `SemanticScholarClient.resolve_target_paper`
2. 再实现 `SemanticScholarClient.fetch_citations`
3. 让阶段 2 服务跑通“真实 Semantic Scholar + fake Crossref enrichment”
4. 再补 `CrossrefClient.fetch_work_by_doi`
5. 最后再补 `search_work_match`

原因：

- `Semantic Scholar` 才是阶段 2 的主链路
- 先跑通主链路，比同时接两个真实客户端更稳

## 6. 工程建议

- 优先自己写薄客户端
- 把外部 API payload 适配到内部中间结构，不要把原始响应直接带进 service 层
- `Semantic Scholar` 和 `Crossref` 都加 timeout、retry、backoff
- `Crossref` 请求尽量带 `mailto`
- `Crossref` 搜索时控制 `rows`，不要在 MVP 阶段做大规模全量拉取

## 官方参考链接

- Semantic Scholar API
  - `https://www.semanticscholar.org/product/api`
- Semantic Scholar tutorial
  - `https://www.semanticscholar.org/product/api/tutorial`
- Crossref REST API
  - `https://www.crossref.org/documentation/retrieve-metadata/rest-api/`
- Crossref REST API tips
  - `https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/`
- Crossref REST API access and authentication
  - `https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/`
- Crossref Cited-by
  - `https://www.crossref.org/documentation/cited-by/`
- Crossref retrieve citations using Cited-by
  - `https://www.crossref.org/documentation//cited-by/retrieve-citations/`

## 当前项目中的使用建议

如果你正在推进阶段 2，实现时优先参考这份文档，再配合：

- `docs/exec-plans/active/2026-04-25-stage2-citation-fetch-agent.md`
- `docs/testing/stage-validation.md`

这份参考文档负责回答“外部源能力边界是什么”，而执行计划负责回答“本项目当前准备怎么落地”。
