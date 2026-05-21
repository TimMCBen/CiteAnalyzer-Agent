# Thesis Crawling and Filtering System

<div align="center">

[![Python Version](https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Gradio-4.37-orange?style=for-the-badge&logo=gradio)](https://www.gradio.app/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](https://opensource.org/licenses/MIT)

</div>

---

[中文](./README.md) | **English**

> Faced with hundreds of newly published papers every day, how can researchers avoid missing important work without being overwhelmed by information overload? This project is designed to tackle exactly that problem.

This is an automated and intelligent academic paper processing workflow designed for researchers. It can automatically crawl the latest papers from arXiv based on predefined keywords, and, via a simple web interface, leverage the semantic understanding capabilities of large language models (LLMs) to perform a **two-stage, customizable deep filtering process**, helping you quickly and accurately locate the most valuable research from massive literature.

## 🌟 Key Features

- **🤖 Fully automated paper retrieval**:  
  Uses the `arxiv` API to automatically fetch and download the latest papers based on predefined keywords. Supports both **full-history crawling** and **daily incremental updates**.  
  A unified conference entry script `conference_crawler.py` is provided, so you can fetch papers from multiple conferences with a single command.

- **🖥️ Elegant visual interface**:  
  Built with Gradio, providing an intuitive and user-friendly web UI. All filtering tasks can be performed **without any command-line operations**.

- **🎯 Two-stage deep filtering**:
  - **Coarse Filtering**: Fast filtering based on **title only**, quickly removing large amounts of irrelevant papers.
  - **Fine Filtering**: Deeper semantic analysis using **title + abstract**, ensuring high relevance of the final results.

- **🔧 No-code logic customization**:  
  The core filtering logic is entirely controlled by **natural language prompts**. You don’t need to modify complex code—just edit a few English sentences in the config file to seamlessly adapt the system to any new research topic.

- **🛡️ Robust multi-round verification**:  
  To avoid missing any potentially relevant paper, the system performs **multiple independent LLM judgments** per batch of data (configurable rounds) and aggregates all results, significantly improving recall.

- **📊 Clear and structured outputs**:  
  After each filtering run, the system generates structured `.json` result files and clear logs/statistics, making subsequent analysis much easier.

---

## 🚀 Quick Start

Follow these three steps to run and experience the system locally.

### 1. Environment Setup

First, make sure `Python 3.9+` and `Git` are installed on your machine.

```bash
# 1. Clone this repository
git clone https://github.com/Takethelead1902/Thesis_Crawling_and_Filtering_System.git

# 2. Enter the project directory
cd Thesis_Crawling_and_Filtering_System

# 3. (Recommended) Create and activate a Python virtual environment
python -m venv venv
# Windows
# venv\Scripts\activate
# macOS / Linux
# source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
````

### 2. Configure API Keys

The filtering functions rely on an external LLM API.

1. In the project root, locate `config.json.example`.
2. **Copy** it and **rename** the copy to `config.json`.
3. Open `config.json` with a text editor and fill in your credentials:

```json
"ai_screener": {
    "api_key": "YOUR_OPENAI_API_KEY",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4-turbo",
    "rounds": 3,
    "max_concurrent": 5
}
```

* `api_key`: **Required.** Your API key from the LLM service provider (e.g., a cloud platform such as Baichuan, Volcano Engine, etc.).
* `base_url`: **Required.** The base URL of the API endpoint (you can directly ask the provider’s AI assistant, “What is the API URL for model X?”).
* `model`: The model name you want to use.
* `rounds`: Number of filtering rounds. `2` or `3` is recommended for a balance of coverage and cost.
* `max_concurrent`: Level of concurrency for API requests. Adjust based on your rate limits.

Other parameters can be configured from the Gradio web UI.

### 3. Launch the App

Once everything is ready, run:

```bash
python filtering_app_after_crawling.py
```

Your browser will automatically open a local URL (e.g. `http://127.0.0.1:5611`), where you’ll see the main interface of the system.

---

## 📖 Usage Guide

### Option A: Try the Filtering Pipeline with Built-in Sample Data

We provide sample data so you can immediately try the core filtering workflow.

1. **Start the app** (as described above).
2. In the web UI, under `请选择要筛选的JSON文件` (“Select JSON file to filter”), the dropdown will automatically list all `.json` files in the project.
3. Choose `arxiv_papers/arxiv_2025_08_llm_papers.json`, which is a raw, unfiltered sample.
4. Click **`执行粗筛`** (“Run Coarse Filtering”) and wait for it to complete. A new file ending in `_coarse_final.json` will be generated in the project root.
5. Click the **`🔄 刷新文件列表`** (“Refresh file list”) button in the top-right corner.
6. In the dropdown, select the newly generated `_coarse_final.json` file.
7. Click **`执行精筛`** (“Run Fine Filtering”) and wait. A final curated list with the suffix `_fine_final.json` will be produced.

---

### Option B: Crawl Your Own Paper Data

If you want to crawl papers for your own topics and then filter them, the system supports two main sources:

---

#### 1️⃣ Crawl and Filter arXiv Papers

The system provides a visual configuration page in the web UI, so you can set crawler parameters **without editing any code**.

##### 🔧 Supported crawling modes

* **`date_range`** – crawl all arXiv papers within a specified start/end date range.
* **`incremental`** – automatically crawl new papers since the last run.

##### 🔍 Advanced keyword queries (recommended)

The interface supports arXiv-style **advanced query syntax**, allowing you to freely combine must / optional keywords.

You can click **“Validate & Preview Query”** to confirm that your query string is valid.

Example UI:

<img src="./screenshot/my_screenshot6.png" style="zoom:50%;" />

After crawling, you can directly select the generated JSON file in the filtering interface and run **coarse** and **fine** filtering.

---

#### 2️⃣ Crawl and Filter Conference Papers (AAAI / NeurIPS / CVPR / ICCV / ACL / ICML / ACMMM)

The system provides a unified entry for conference paper crawling. Currently supported conferences (2024 & 2025):

* **AAAI**
* **NeurIPS**
* **CVPR**
* **ICCV**
* **ACL**
* **ICML**
* **ACMMM**

##### ▶ Usage

Run the following command to crawl a target conference (format: `Conference-Year`):

```bash
python conference_crawler.py \
    --conf ACMMM-2024 \
    --proxy http://10.10.10.10:7897 \
    --outdir ./conference_papers/
```

> Note: The script name here has been unified as `conference_crawler.py`.

---

### ✨ Customize Your Own Filtering Assistant

This is the core idea of the project: **you define the filtering logic in plain language**.

1. Open `filtering_app_after_crawling.py`.
2. At the top of the file, locate the two variables: `COARSE_SYSTEM_PROMPT` and `FINE_SYSTEM_PROMPT`.
3. **Modify the string contents** to describe your new filtering criteria. For example, switching from “emotional support” to “autonomous driving”:

```python
# Original prompt (emotional support)
COARSE_SYSTEM_PROMPT = """
Determine if this paper title is related to emotional support, psychological counseling, or multi-turn dialogue. Return True if it is, otherwise return False.
<True/False>
"""

# Modified prompt (autonomous driving)
COARSE_SYSTEM_PROMPT = """
Determine if the paper's title is about autonomous driving or vehicle perception. If it mentions topics like LiDAR, sensor fusion, path planning, or self-driving, return True. Otherwise, return False.
<True/False>
"""
```

4. Save the file and **restart** `filtering_app_after_crawling.py`.
   Your system is now using a completely new set of filtering rules.

---

## 🖼️ Screenshots

### 1. Backend arXiv crawler running view

<img src="./screenshot/my_screenshot1.png" style="zoom:50%;" />

### 2. Filtering system – configuration page

<img src="./screenshot/my_screenshot2.png" alt="image-20250827232230500" style="zoom:60%;" />

### 3. Filtering system – coarse filtering

![image-20250827232519246](./screenshot/my_screenshot3.png)

### 4. Filtering system – fine filtering

![image-20250827232627223](./screenshot/my_screenshot4.png)

### 5. Filtering system – help page

<img src="./screenshot/my_screenshot5.png" alt="image-20250827232810220" style="zoom:80%;" />

---

## 📂 Project Structure & Data

```text
/
├── 📂 arxiv_papers/                       # Directory for crawled arXiv papers
│   └── 📜 arxiv_2025_08_llm_papers.json   #  -> [input] Raw, unfiltered data
│
├── 📂 conference_papers/                  # Directory for crawled conference papers
│   └── 📜 conference_papers/AAAI_***.json
│
├── 📂 results/
│   └── 📜 arxiv_2025_08_llm_papers_coarse_final.json  # -> [output] Coarse-filtered result
│
├── 📂 src/                                # Module scripts
│   ├── 🐍 ...
│
├── 🐍 arxiv_crawler.py                    # Core script: arXiv crawler
├── 🐍 conference_crawler.py               # Core script: conference crawler
├── 🐍 filtering_app_after_crawling.py     # Core script: Gradio web app
│
├── 📄 config.json.example                 # API config example (copy to config.json)
├── 📄 requirements.txt                    # Python dependency list
├── 📄 .gitignore                          # Git ignore rules
├── 📄 LICENSE                             # MIT license
└── 📄 README.md                           # This documentation
```

---

## ⚠️ Known Issues

### 1. Conference keyword matching is currently inactive

At the moment, the **keyword matching system in the web UI only applies to the arXiv crawler**.

Conference papers fetched via `conference_crawler.py` are **all written directly to local JSON files**. No keyword-based filtering is applied at the crawling stage.

#### Recommended workflow:

1. Use `conference_crawler.py` to fetch **all papers from the target conference**.
2. In the filtering interface, apply:

   * **Coarse filtering (Title Filtering)**
   * **Fine filtering (Title + Abstract Filtering)**

Because the official arXiv search API provides built-in features like **synonym expansion and semantic matching**, which the local conference crawlers cannot easily replicate, it is **not recommended** to perform keyword filtering at the conference crawling stage.

> Recommended approach: For conference papers, always fetch **full data** first, then run the two-stage filtering (“coarse → fine”) in the UI for more reliable results.

---

### 2. ACMMM 2025 abstracts cannot be fully crawled

Since **ACMMM 2025 is not yet available on OpenReview**, the current pipeline works as follows:

* Crawl basic paper information from the **official ACMMM conference website**.
* Search arXiv by **title** to fill in abstracts wherever possible.

However, there are limitations:

* The official ACM/ACMMM website can be difficult to access (validation, rate-limiting, anti-bot mechanisms).
* arXiv does **not** host all ACMMM 2025 papers.
* As a result, for some papers:

  * The `abstract` field may be empty.
  * The abstract may be incomplete or truncated.

The current script will preserve as much information as it can obtain, but **cannot guarantee 100% completeness for ACMMM 2025 abstracts**.

#### Suggested handling:

* For important papers, manually click or open the `url` field in the JSON (if present).
* Visit the **official ACM page or arXiv page** to read the full abstract.
* Manually supplement or store the complete text if necessary.

---

If you encounter similar issues for other conferences, feel free to propose improvements or contribute patches.
