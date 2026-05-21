# Thesis Crawling and Filtering System (论文爬取与智能筛选系统)

<div align="center">

[![Python Version](https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Gradio-4.37-orange?style=for-the-badge&logo=gradio)](https://www.gradio.app/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](https://opensource.org/licenses/MIT)

</div>

---

**中文** | [English](./README_EN.md)

 > 面对每日数以百计的新发表论文，研究人员如何才能不错过关键研究，同时又不被信息洪流淹没？本项目旨在解决这一痛点。

这是一个为科研人员设计的自动化、智能化的学术论文处理工作流。它能够自动从arXiv上抓取符合特定关键词的最新论文，并通过一个简洁的Web界面，利用大型语言模型（LLM）的强大语义理解能力，帮助用户进行两阶段、可定制化的深度筛选，从而在海量文献中快速、精准地定位到最具价值的研究成果。

## 🌟 核心功能 (Key Features)

- **🤖 全自动论文获取**: 基于预设关键词，通过 `arxiv` API 自动爬取并下载最新的学术论文，支持全量历史数据抓取与每日增量更新。提供统一会议入口脚本 `conference_crawler.py`，一条命令即可拉取多个会议的论文。

- **🖥️ 优雅的可视化界面**: 采用 Gradio 构建，提供了一个直观、友好的Web用户界面，无需任何命令行操作即可完成所有筛选任务。

-   **🎯 两阶段深度筛选**:
    -   **粗筛 (Coarse Filtering)**: 基于论文**标题**进行快速筛选，迅速剔除大量不相关文献。
    -   **精筛 (Fine Filtering)**: 结合**标题与摘要**进行深度语义分析，确保筛选结果的高度相关性。
    
- **🔧 无代码逻辑定制**: 筛选的核心标准完全由**自然语言提示词 (Prompt)** 控制。用户无需修改任何复杂代码，只需编辑配置文件中的几句英文描述，即可将系统无缝切换至任何新的研究领域。

- **🛡️ 鲁棒的多轮验证**: 为确保不错过任何一篇潜在相关论文，系统会对每批数据进行多轮（可配置）独立的LLM判断，并综合所有结果，极大提升了召回率。

- **📊 清晰的结果输出**: 每次筛选后，系统都会生成结构化的 `.json` 结果文件，并提供清晰的日志和统计数据，方便用户进行后续分析。

  

## 🚀 快速上手 (Quick Start)

您只需遵循以下三个步骤，即可在本地运行并体验本系统的完整功能。

### 1. 环境配置 (Setup)

首先，确保您的电脑已安装 `Python 3.9+` 和 `Git`。

```bash
# 1. 克隆本仓库到您的本地设备
git clone [https://github.com/Takethelead1902/Thesis_Crawling_and_Filtering_System.git](https://github.com/Takethelead1902/Thesis_Crawling_and_Filtering_System.git)

# 2. 进入项目目录
cd Thesis_Crawling_and_Filtering_System

# 3. (推荐) 创建并激活一个Python虚拟环境
python -m venv venv
# Windows
# venv\Scripts\activate
# macOS / Linux
# source venv/bin/activate

# 4. 安装所有必需的依赖库
pip install -r requirements.txt
```

### 2. 配置API密钥 (API Configuration)

本系统的筛选功能依赖于大型语言模型（LLM）的API。

1. 在项目根目录下，找到 `config.json.example` 文件。
2. **复制**该文件并**重命名**为 `config.json`。
3. 使用文本编辑器打开 `config.json` 并填入您的个人信息：

```
"ai_screener": {
    "api_key": "YOUR_OPENAI_API_KEY",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4-turbo",
    "rounds": 3,
    "max_concurrent": 5
}
```

- `api_key`: **必需**。您的LLM服务提供商的API密钥。（这个需要您去例如百炼、火山引擎这种模型云平台去申请一下）
- `base_url`: **必需**。API的请求地址。（到了申请的地方你可以直接问相关平台的ai助手你调用的模型名称对应的api_url是怎么样的）
- `model`: 您希望使用的模型名称。
- `rounds`: 筛选时进行的轮次，推荐 `2` 或 `3` 以保证结果的全面性。
- `max_concurrent`: 并发请求数量，请根据您的API速率限制进行调整。

其余参数可以在gradio网页中配置。

### 3. 启动应用 (Launch)

一切准备就绪！在您的终端中运行以下命令：

```
python filtering_app_after_crawling.py
```

执行后，浏览器将自动打开一个本地网址 (如 `http://127.0.0.1:5611`)，您将看到本系统的操作界面。



## 📖 使用指南 (How to Use)

### 选项 A：体验筛选功能 (使用自带样本)

我们已为您准备好了样本数据，让您可以立即体验核心的筛选功能。

1. **启动应用** (如上一步所示)。
2. 在Web界面中，`请选择要筛选的JSON文件` 下拉菜单会自动加载项目中的所有 `.json` 文件。
3. 选择 `arxiv_papers/arxiv_2025_08_llm_papers.json`，这是一个原始的、未经筛选的论文数据样本。
4. 点击 **`执行粗筛`** 按钮，并等待任务完成。完成后，项目根目录将生成一个 `_coarse_final.json` 后缀的新文件。
5. 点击界面右上角的 **`🔄 刷新文件列表`** 按钮。
6. 在下拉菜单中，选择上一步生成的 `_coarse_final.json` 文件。
7. 点击 **`执行精筛`** 按钮，等待任务完成。最终，您将得到一个 `_fine_final.json` 后缀的精选论文列表文件。

### 选项 B：爬取您自己的论文数据

如果您希望抓取特定主题的论文并进行筛选，本系统支持两种来源方式：

---

#### 1️⃣ 爬取并筛选 arXiv 论文

系统提供可视化 Web 配置界面，允许用户无需修改代码即可直接设置爬虫参数。

##### 🔧 支持的爬取模式

- **`date_range`**：爬取指定起止日期范围内的全部 arXiv 论文  
- **`incremental`**：基于上一次爬取时间，自动增量抓取最新论文

#### 🔍 高级关键词查询（推荐）

界面支持 arXiv 风格的 **高级查询语法**，可自由组合 must / optional 关键词。

您可以点击 **“验证并预览查询”** 来确认关键词语法是否合法。

示例界面：

<img src="./screenshot/my_screenshot6.png" style="zoom:50%;" />

完成爬取后，您可以直接在筛选界面中选择生成的 JSON 文件进行粗筛和精筛。

---

#### 2️⃣ 爬取并筛选会议论文（AAAI / NeurIPS / CVPR / ICCV / ACL / ICML / ACMMM）

本系统提供统一的会议论文爬虫入口，支持以下会议（2024 & 2025 年）：

- **AAAI**
- **NeurIPS**
- **CVPR**
- **ICCV**
- **ACL**
- **ICML**
- **ACMMM**

##### ▶ 使用方式

运行以下命令即可爬取对应会议论文（格式：`会议-年份`）：

```bash
python unified_conference_entry.py \
    --conf ACMMM-2024 \
    --proxy http://10.10.10.10:7897 \
    --outdir ./conference_papers/
```

### ✨ 定制您的专属筛选助手 (Customize Your Filter)

这是本项目的精髓所在。您可以完全通过自然语言来定义筛选标准。

1. 打开 `filtering_app_after_crawling.py` 文件。
2. 定位到文件顶部的 `COARSE_SYSTEM_PROMPT` 和 `FINE_SYSTEM_PROMPT` 两个变量。
3. **修改这两个字符串的内容**，以描述您新的筛选要求。例如，从情感支持领域切换到自动驾驶领域：
   ```
   # 原Prompt (情感支持)
   COARSE_SYSTEM_PROMPT = """
   Determine if this paper title is related to emotional support, psychological counseling, or multi-turn dialogue. Return True if it is, otherwise return False.
   <True/False>
   """
   
   # 修改后的Prompt (自动驾驶)
   COARSE_SYSTEM_PROMPT = """
   Determine if the paper's title is about autonomous driving or vehicle perception. If it mentions topics like LiDAR, sensor fusion, path planning, or self-driving, return True. Otherwise, return False.
   <True/False>
   """
   ```
4. 保存文件并**重启** `filtering_app_after.py` 脚本，您的筛选系统现在就以全新的标准工作了！


## 🖼️ 界面截图 (Screenshots)

### 1. 后台爬取arxiv您对应需求下的论文的运行界面

<img src="./screenshot/my_screenshot1.png" style="zoom:50%;" />

### 2. 论文筛选系统---配置界面

<img src="./screenshot/my_screenshot2.png" alt="image-20250827232230500" style="zoom:60%;" />

### 3. 论文筛选系统---粗筛界面

![image-20250827232519246](./screenshot/my_screenshot3.png)

### 4. 论文筛选系统---精排界面

![image-20250827232627223](./screenshot/my_screenshot4.png)

### 5.论文筛选系统---帮助界面

<img src="./screenshot/my_screenshot5.png" alt="image-20250827232810220" style="zoom:80%;" />


## 📂 项目结构与数据说明 (Project Structure & Data)

```
/
├── 📂 arxiv_papers/                     # 存放爬取论文的目录
│   └── 📜 arxiv_2025_08_llm_papers.json #  -> [输入] 原始的、未筛选的爬取数据
│
├── 📂 conference_papers/ # 存放爬取会议论文的目录
│   └── 📜 conference_papers/AAAI_***.json
│
├── 📂 results/
│   └── 📜 arxiv_2025_08_llm_papers_coarse_final.json  # -> [输出] 对原始样本粗筛
│
├── 📂 src/                              # 各模块脚本文件
│   ├── 🐍 ...
│
├── 🐍 arxiv_crawler.py                  # 核心脚本：arXiv 论文爬虫
├── 🐍 conference_crawler.py             # 核心脚本：会议论文爬虫
├── 🐍 filtering_app_after_crawling.py   # 核心脚本：Gradio Web 应用
│
├── 📄 config.json.example             # API配置示例文件，需重命名为 config.json
├── 📄 requirements.txt                # Python 依赖包列表
├── 📄 .gitignore                        # Git 忽略规则文件
├── 📄 LICENSE                         # MIT 开源许可证
└── 📄 README.md                         # 本说明文档
```

## ⚠️ 已知问题 (Known Issues)

### 1. Conference 关键词匹配当前无效

目前 Web 界面中配置的 **关键词匹配系统仅对 arXiv 爬虫生效**。

通过 `conference_crawler.py` 获取的会议论文会 **全部写入本地 JSON**，爬取阶段不会根据关键词进行过滤。

#### 建议流程：

1. 使用 `conference_crawler.py` 拉取 **全量会议论文**  
2. 在筛选界面中对该 JSON 文件执行：  
   - **粗筛（Title Filtering）**  
   - **精筛（Title + Abstract Filtering）**  

由于 arXiv 官方搜索接口内置了“近义词扩展与语义匹配”，而本地会议爬虫无法提供同等能力，因此 **不建议在会议论文爬取阶段使用关键词过滤**。

> 推荐做法：对于 Conference 论文，请直接拉取全量数据，并在筛选界面执行「粗筛 → 精筛」的两阶段过滤，以获得更可靠的筛选效果。



---

### 2. ACMMM 2025 摘要无法完全爬取

由于 ACMMM 2025 **尚未在 OpenReview 发布**，目前的爬取流程采用：

- **ACM 官方会议网站爬取论文基本信息**  
- **在 arXiv 上搜索对应标题以补全摘要**

但存在如下限制：

- **ACM 官方网站访问难度高（验证/限流/反爬策略）**
- **arXiv 并未收录 ACMMM 2025 的全部论文**
- 因此部分论文的：
  - `abstract` 字段可能为空  
  - 摘要可能不完整或被截断  

当前脚本会尽最大努力保留可获取内容，但 **无法保证 ACMMM 2025 摘要 100% 完整**。

#### 建议处理方式：

- 如遇重要论文，请手动点击 JSON 中的 `url` 字段  
- 进入 **ACM 官方页面或 arXiv 页面**查看完整摘要  
- 必要时可自行补全或保存提取内容  

---

如果你遇到其它会议类似问题，也欢迎进一步反馈优化方案。

## TODO:

[-] 更新json文件时不会更新到网页