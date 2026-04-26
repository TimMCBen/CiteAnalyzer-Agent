# 阶段验证说明

当前仓库把 MVP 的阶段验证脚本放在 `scripts/test_agent/`。

## 入口

- 项目级统一入口：`bash ./scripts/check-project.sh`
- 阶段聚合入口：`python ./scripts/test_agent/run.py`
- 阶段 1 单独运行：`python ./scripts/test_agent/stage1.py`

## 当前覆盖

### 阶段 1

- 脚本：`scripts/test_agent/stage1.py`
- 覆盖：
  - 标题线索请求
  - DOI 请求
  - arXiv 请求
  - OpenAlex 论文 ID 请求
  - 非论文被引分析请求

### 阶段 2 到阶段 8

- 阶段 2
  - 脚本：`scripts/test_agent/stage2.py`
  - 覆盖：
    - 多源记录合并与去重
    - 来源追踪输出
    - 单来源失败时的部分结果降级
    - 可选 live smoke（通过 `STAGE2_LIVE=1` 与 `STAGE2_TARGET_DOI` 启用）
    - 已验证的真实样本：`10.1145/3368089.3409740`

- 阶段 3、阶段 4、阶段 7、阶段 8
  - 目录中已预留：
    - `stage3.py`
    - `stage4.py`
    - `stage7.py`
    - `stage8.py`
  - 当前状态：TODO，占位保留给后续阶段实现时补齐。

- 阶段 5
  - 脚本：`scripts/test_agent/stage5.py`
  - 覆盖：
    - 直接读取已保存的阶段 2 真实样本：`docs/generated/stage2-live-10.1145.3368089.3409740.json`
    - 使用本地 PDF / HTML / LaTeX 文件夹具验证全文抓取与文本解析
    - 覆盖无全文样本返回空结果
    - 可选 live smoke：
      - `STAGE5_FETCH_LIVE=1 python ./scripts/test_agent/stage5.py`
      - 验证真实 `arXiv` 优先全文抓取与解析入口

- 阶段 6
  - 脚本：`scripts/test_agent/stage6.py`
  - 覆盖：
    - 直接读取已保存的阶段 2 真实样本：`docs/generated/stage2-live-10.1145.3368089.3409740.json`
    - 使用本地 PDF / HTML / LaTeX 文件夹具走真实解析链路
    - 默认直接调用真实 LLM 做参考文献匹配、正文窗口定位和情感分类
    - 覆盖 `positive` / `neutral` / `critical` / `unknown` 四类标签
    - 覆盖“先在参考文献中识别目标条目，再回正文定位引文号”的主链路
    - 可选 live smoke：
      - `STAGE6_LIVE=1 python ./scripts/test_agent/stage6.py`
      - 验证真实 LLM zero-shot 引文定位
      - `STAGE6_FETCH_LIVE=1 python ./scripts/test_agent/stage6.py`
      - 验证真实 `arXiv` 优先全文抓取与解析入口

## 维护原则

- 阶段测试脚本属于项目实现层，不应直接写进模板级 `CICD` 说明。
- 新增项目测试入口时，优先更新本目录，再决定是否需要把入口接入 `scripts/check-project.sh`。
- execution plan 中的阶段验证任务应和这里保持一致。
