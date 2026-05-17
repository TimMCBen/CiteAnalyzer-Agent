## [2026-05-17 12:15] | Task: 中文化阶段6大模型提示词

### 🤖 Execution Context

- **Agent ID**: `Codex`
- **Base Model**: `GPT-5`
- **Runtime**: `Codex CLI`

### 📥 User Query

> 把阶段6发给大模型的提示词改成中文，并保留已有结构化输出兼容性。

### 🛠 Changes Overview

**Scope:** 阶段6引用定位 / 情感判断、报告展示、测试脚本

**Key Actions:**

- **[中文化 LLM prompt]**: 将参考文献匹配、正文上下文选择和引用情感分类的 system prompt 改为中文。
- **[保留机器契约]**: 继续使用英文枚举 `positive/neutral/critical/unknown` 和英文 evidence 前缀，避免破坏现有 JSON 与测试。
- **[报告展示优化]**: HTML citation card 将情感标签显示为 `正向/中性/批评/未知`，JSON 仍保留英文原值。
- **[补验证]**: 新增 focused prompt contract，验证中文 prompt 约束、中文 `evidence_note` 和英文机器前缀可同时成立。

### 🧠 Design Intent (Why)

用户阅读报告时主要需要中文解释，但下游测试和数据契约依赖英文枚举与 evidence 前缀。本次采用展示层和自然语言层中文化，保留结构化字段英文，降低回归风险。

### 📁 Files Modified

- `packages/sentiment/classifier.py`
- `packages/sentiment/llm_locator.py`
- `packages/reporting/service.py`
- `scripts/test_agent/llm_prompt_contract.py`
- `scripts/test_agent/run.py`
- `scripts/test_agent/run_contract.py`
- `scripts/test_agent/stage7.py`
