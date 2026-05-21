import gradio as gr
import threading
import time

from src.config_manager import config_manager
from .utils import get_json_files, get_result_files
from .ai_screener import run_coarse_screening_with_progress, run_fine_screening_with_progress
from ..visualization import dashboard
from ..utils import get_gradio_logs, clear_gradio_logs
from arxiv_crawler import run_crawler_logic
from ..crawler.query_translator import translate_simplified_query

def create_interface(papers_df, all_keywords):
    def toggle_source_group(mode):
        is_conf = (mode == "conference")
        return (
            gr.update(visible=is_conf),      # conference_group
            gr.update(visible=not is_conf)   # arxiv_mode_group
        )
    """创建并返回Gradio应用界面。"""
    with gr.Blocks(title="论文筛选与可视化系统", theme=gr.themes.Soft()) as app:
        gr.Markdown("# 📚 论文筛选与可视化系统")
        
        with gr.Tabs():
            # --- 配置标签页 ---
            with gr.TabItem("⚙️ 配置"):
                with gr.Tabs():
                    with gr.TabItem("🤖 AI 筛选器配置"):
                        gr.Markdown("### AI Screening Configuration")
                        gr.Markdown("在这里修改的配置将实时保存到 `config.json`。")
                        
                        filtering_config = config_manager.get_config("filtering")
                        ai_screener_config = filtering_config.get("ai_screener", {})
                        
                        with gr.Row():
                            with gr.Column():
                                api_key_input = gr.Textbox(label="API Key", info="用于访问大模型的API密钥", value=ai_screener_config.get("api_key"), type="password")
                                base_url_input = gr.Textbox(label="Base URL", info="大模型的API端点地址", value=ai_screener_config.get("base_url"))
                                model_input = gr.Textbox(label="模型名称", info="要使用的具体模型，例如 'gpt-4-turbo'", value=ai_screener_config.get("model"))
                            
                            with gr.Column():
                                rounds_input = gr.Slider(label="处理轮数", info="AI筛选执行的轮数，以提高结果稳定性", minimum=1, maximum=10, step=1, value=ai_screener_config.get("rounds", 3))
                                max_concurrent_input = gr.Slider(label="最大并发数", info="同时向API发送请求的最大数量", minimum=1, maximum=200, step=1, value=ai_screener_config.get("max_concurrent", 50))

                    with gr.TabItem("🕷️ 爬虫配置"):
                        gr.Markdown("### ArXiv Or Conference Crawler Configuration")
                        crawler_config = config_manager.get_config("crawler")
                        date_range_cfg = crawler_config.get("date_range", {})
                        keywords_cfg = crawler_config.get("keywords", {})
                        arxiv_params_cfg = crawler_config.get("arxiv_params", {})
                        proxy_cfg = crawler_config.get("proxy", {})

                        source_selector = gr.Radio(
                            ["arxiv", "conference"],
                            value=crawler_config.get("source", "arxiv"),
                            label="数据源类型",
                            info="选择爬取 ArXiv（在线 API），或使用本地会议 JSON 数据（conference 模式）"
                        )

                        # 会议模式额外设置
                        with gr.Group(visible=(crawler_config.get("source", "arxiv") == "conference")) as conference_group:
                            conf_params = crawler_config.get("conference_params", {})
                            conference_names_input = gr.Textbox(
                                label="会议名称（可多个）",
                                info="例如: ICCV-2025, CVPR-2024",
                                value=", ".join(conf_params.get("names", []))
                            )
                            conference_path_input = gr.Textbox(
                                label="会议 JSON 目录",
                                info="例如: ./conference_data",
                                value=conf_params.get("source_path", "./conference_data")
                            )
                        with gr.Group(visible=(crawler_config.get("source", "arxiv") == "arxiv")) as arxiv_mode_group:
                            with gr.Row():
                                crawl_mode_input = gr.Dropdown(
                                    label="爬取模式",
                                    info="选择 'incremental' 进行每日增量爬取，或 'date_range' 进行一次性范围爬取",
                                    choices=["incremental", "date_range"],
                                    value=crawler_config.get("crawl_mode")
                                )
                                start_date_cfg = gr.Textbox(
                                    label="开始日期 (范围模式)",
                                    info="格式: YYYY-MM-DD",
                                    value=date_range_cfg.get("start_date")
                                )
                                end_date_cfg = gr.Textbox(
                                    label="结束日期 (范围模式)",
                                    info="格式: YYYY-MM-DD",
                                    value=date_range_cfg.get("end_date")
                                )
                        
                        source_selector.change(
                            fn=toggle_source_group,
                            inputs=[source_selector],
                            outputs=[conference_group, arxiv_mode_group]
                        )
                        gr.Markdown("---")
                        
                        query_mode_selector = gr.Radio(
                            ["简单模式", "高级模式"], 
                            value="简单模式" if crawler_config.get("query_mode", "simple") == "simple" else "高级模式",
                            label="关键词查询模式", 
                            info="选择“简单模式”以使用预设的'must'/'optional'字段，或选择“高级模式”以编写自定义查询。"
                        )

                        with gr.Group(visible=crawler_config.get("query_mode", "simple") == "simple") as simple_query_group:
                            keywords_must_input = gr.Textbox(label="必须包含的关键词", info="用英文逗号 ',' 分隔。论文必须至少匹配其中一个", value=", ".join(keywords_cfg.get("must", [])))
                            keywords_optional_input = gr.Textbox(label="可选关键词", info="用英文逗号 ',' 分隔。用于扩大搜索范围", value=", ".join(keywords_cfg.get("optional", [])))

                        with gr.Group(visible=crawler_config.get("query_mode", "simple") == "advanced") as advanced_query_group:
                            advanced_query_input = gr.Textbox(
                                label="高级查询语句", 
                                info="使用自定义语法: title:word, abs:word, AND, OR, NOT, ()", 
                                value=crawler_config.get("advanced_query", ""),
                                lines=5
                            )
                            with gr.Row():
                                validate_query_btn = gr.Button("🔍 验证并预览查询")
                                query_validation_status = gr.Textbox(label="验证结果", interactive=False)

                        gr.Markdown("---")
                        with gr.Row():
                            max_results_input = gr.Slider(label="每页最大结果数", info="每次API请求获取的论文数量", minimum=10, maximum=500, step=5, value=arxiv_params_cfg.get("max_results_per_request"))
                            base_delay_input = gr.Slider(label="请求延迟（秒）", info="两次API请求之间的间隔时间", minimum=5, maximum=60, step=1, value=arxiv_params_cfg.get("base_delay"))
                            max_retries_input = gr.Slider(label="最大重试次数", info="API请求失败时的最大重试次数", minimum=1, maximum=10, step=1, value=arxiv_params_cfg.get("max_retries"))
                            check_hour_input = gr.Slider(label="每日检查时间（小时）", info="在增量模式下，每天执行任务的小时 (24小时制)", minimum=0, maximum=23, step=1, value=arxiv_params_cfg.get("incremental_check_hour"))

                        gr.Markdown("---")
                        with gr.Row():
                            http_proxy_input = gr.Textbox(label="HTTP 代理", info="例如: http://user:pass@host:port", value=proxy_cfg.get("http"))
                            https_proxy_input = gr.Textbox(label="HTTPS 代理", info="例如: https://user:pass@host:port", value=proxy_cfg.get("https"))

                save_config_btn = gr.Button("💾 保存所有配置", variant="primary")
                config_status = gr.Textbox(label="状态", interactive=False)

            # --- 爬虫标签页 ---
            with gr.TabItem("🕷️ 爬虫"):
                gr.Markdown("### 爬虫实时日志")
                log_display = gr.Textbox(label="日志输出", lines=20, interactive=False, autoscroll=True)
                
                with gr.Row():
                    run_crawler_btn = gr.Button("🚀 启动爬虫", variant="primary")
                    clear_log_btn = gr.Button("🗑️ 清空日志")

                log_state = gr.State("")

                def stream_logs(current_logs):
                    new_logs = get_gradio_logs()
                    if new_logs:
                        updated_logs = current_logs + "\n" + new_logs if current_logs else new_logs
                        return updated_logs, updated_logs
                    return current_logs, gr.update()

                app.load(
                    stream_logs,
                    inputs=[log_state],
                    outputs=[log_state, log_display],
                    every=1
                )

                def run_crawler_in_background():
                    clear_gradio_logs()
                    
                    def crawler_task():
                        try:
                            run_crawler_logic()
                        except Exception as e:
                            # 确保即使爬虫主函数崩溃，错误也能被记录到Gradio日志
                            import logging
                            logging.error(f"爬虫主线程发生严重错误: {e}", exc_info=True)

                    thread = threading.Thread(target=crawler_task)
                    thread.start()
                    return "爬虫已在后台启动..."

                run_crawler_btn.click(
                    run_crawler_in_background,
                    outputs=[log_display]
                )

                def clear_logs_display():
                    clear_gradio_logs()
                    return "", ""

                clear_log_btn.click(
                    clear_logs_display,
                    outputs=[log_state, log_display]
                )

            # --- 粗筛标签页 ---
            with gr.TabItem("🔍 粗筛"):
                gr.Markdown("### 粗筛阶段")
                with gr.Row():
                    with gr.Column(scale=1):
                        main_file_dropdown = gr.Dropdown(choices=get_json_files(), label="主会议论文文件")
                        main_file_upload = gr.File(label="或上传文件", file_types=[".json"])
                        findings_file_dropdown = gr.Dropdown(choices=[""] + get_json_files(), label="Findings论文文件（可选）")
                        findings_file_upload = gr.File(label="或上传文件", file_types=[".json"])
                        refresh_files_btn = gr.Button("🔄 刷新文件列表")
                    with gr.Column(scale=2):
                        ai_screener_cfg = config_manager.get_config("filtering").get("ai_screener", {})
                        coarse_prompt_value = ai_screener_cfg.get("coarse_prompt", "默认粗筛提示词")
                        coarse_prompt = gr.Textbox(label="粗筛提示词", value=coarse_prompt_value, lines=8)
                        with gr.Row():
                            run_coarse_btn = gr.Button("🚀 开始粗筛", variant="primary", scale=3)
                            save_coarse_prompt_btn = gr.Button("💾 保存提示词", scale=1)
                
                coarse_output = gr.Textbox(label="粗筛结果", lines=12, interactive=False)
                
                run_coarse_btn.click(
                    run_coarse_screening_with_progress,
                    inputs=[main_file_dropdown, findings_file_dropdown, main_file_upload, findings_file_upload, coarse_prompt],
                    outputs=coarse_output
                )

            # --- 精排标签页 ---
            with gr.TabItem("🎯 精排"):
                gr.Markdown("### 精排阶段")
                with gr.Row():
                    with gr.Column(scale=1):
                        input_file_dropdown = gr.Dropdown(choices=get_result_files(), label="粗筛结果文件")
                        input_file_upload = gr.File(label="或上传文件", file_types=[".json"])
                        refresh_input_files_btn = gr.Button("🔄 刷新结果文件")
                    with gr.Column(scale=2):
                        ai_screener_cfg = config_manager.get_config("filtering").get("ai_screener", {})
                        fine_prompt_value = ai_screener_cfg.get("fine_prompt", "默认精排提示词")
                        fine_prompt = gr.Textbox(label="精排提示词", value=fine_prompt_value, lines=10)
                        with gr.Row():
                            run_fine_btn = gr.Button("🎯 开始精排", variant="primary", scale=3)
                            save_fine_prompt_btn = gr.Button("💾 保存提示词", scale=1)
                
                fine_output = gr.Textbox(label="精排结果", lines=12, interactive=False)
                
                run_fine_btn.click(
                    run_fine_screening_with_progress,
                    inputs=[input_file_dropdown, input_file_upload, fine_prompt],
                    outputs=fine_output
                )

            # --- 可视化看板标签页 ---
            with gr.TabItem("📊 结果看板"):
                gr.Markdown("### 论文可视化筛选")
                with gr.Row():
                    with gr.Column(scale=1, min_width=300):
                        gr.Markdown("#### 筛选条件")
                        start_date_input = gr.Textbox(label="开始日期", info="格式: YYYY-MM-DD")
                        end_date_input = gr.Textbox(label="结束日期", info="格式: YYYY-MM-DD")
                        keyword_selector = gr.Dropdown(
                            label="关键词筛选", choices=all_keywords, multiselect=True
                        )
                        with gr.Row():
                            filter_btn = gr.Button("🔍 应用筛选", variant="primary")
                            refresh_dashboard_btn = gr.Button("🔄 刷新看板数据")
                        status_text = gr.Markdown(f"已加载 **{len(papers_df)}** 篇论文。")
                    with gr.Column(scale=3):
                        gr.Markdown("#### 筛选结果")
                        paper_display_area = gr.Markdown("点击“应用筛选”以显示结果。")
                
                filter_btn.click(
                    fn=dashboard.filter_and_display_papers,
                    inputs=[start_date_input, end_date_input, keyword_selector],
                    outputs=[paper_display_area]
                )
            # --- 帮助标签页 ---
            with gr.TabItem("❓ 帮助"):
                gr.Markdown("""
                ### 📖 系统使用指南

                欢迎使用论文筛选与可视化系统！本系统旨在帮助您自动化地从 arXiv 等来源爬取、筛选和分析学术论文。以下是详细的工作流程和各模块功能说明。

                ---

                #### 🚀 推荐工作流程

                1.  **首次配置 (⚙️ 配置)**:
                    *   在 **AI 筛选器配置** 中，填入您的大语言模型 API Key、Base URL 和模型名称。
                    *   在 **爬虫配置** 中，根据您的网络环境设置代理（如果需要）。选择您偏好的查询模式（建议初次使用时选择 **简单模式**），并填入您研究领域的核心关键词。
                    *   点击 **💾 保存所有配置** 按钮。

                2.  **执行爬取 (🕷️ 爬虫)**:
                    *   切换到 **爬虫** 标签页。
                    *   点击 **🚀 启动爬虫**。系统将根据您的配置（增量或日期范围）开始在后台获取论文。您可以在日志区看到实时进度。
                    *   爬取完成后，原始数据会以 JSON 格式保存在 `arxiv_papers/` 目录下。

                3.  **AI 粗筛 (🔍 粗筛)**:
                    *   切换到 **粗筛** 标签页。
                    *   在 **主会议论文文件** 下拉菜单中，选择刚刚爬取到的 JSON 文件。
                    *   检查或修改 **粗筛提示词**，然后点击 **🚀 开始粗筛**。AI 将根据论文标题快速淘汰不相关的结果。

                4.  **AI 精排 (🎯 精排)**:
                    *   粗筛完成后，切换到 **精排** 标签页。
                    *   在 **粗筛结果文件** 下拉菜单中，选择上一步生成的 `_coarse_final.json` 文件。
                    *   检查或修改 **精排提示词**，然后点击 **🎯 开始精排**。AI 将结合标题和摘要进行更深入的分析和打分。

                5.  **可视化分析 (📊 结果看板)**:
                    *   精排完成后，切换到 **结果看板** 标签页。
                    *   点击 **🔄 刷新看板数据** 以加载最新的筛选结果。
                    *   您现在可以使用日期和关键词筛选器来交互式地探索和分析您感兴趣的论文。

                ---

                #### 🧩 各模块功能详解

                *   **⚙️ 配置**:
                    *   **AI 筛选器**: 管理用于筛选论文的大语言模型（LLM）的认证信息和参数。`处理轮数` 和 `最大并发数` 是性能调优选项，可以平衡速度和稳定性。
                    *   **爬虫**:
                        *   **爬取模式**: `incremental` 会按设定的每日检查时间自动拉取最新论文；`date_range` 则用于一次性爬取指定时间范围内的历史论文。
                        *   **关键词查询模式**: `简单模式` 通过“必须包含”和“可选”关键词自动生成查询；`高级模式` 允许您使用 `title:word`, `abs:word`, `AND`, `OR`, `NOT` 等操作符构建复杂的布尔查询。

                *   **🕷️ 爬虫**:
                    *   显示爬虫运行时的实时日志，包括正在爬取的查询、API 请求状态、遇到的错误等。是监控爬虫健康状况的重要窗口。

                *   **🔍 粗筛 / 🎯 精排**:
                    *   这两个模块是 AI 筛选的核心。您可以自定义提示词（Prompt）来指导 AI 的筛选标准。例如，您可以要求 AI 关注特定的技术、方法或应用场景。
                    *   点击 **💾 保存提示词** 可以将您优化后的提示词更新到 `config.json` 文件中，方便日后使用。

                *   **📊 结果看板**:
                    *   一个交互式的数据看板，用于最终结果的探索。您可以快速过滤出特定时间段或包含特定关键词的论文，并查看其核心信息。
                """)
                def refresh_dashboard_data():
                    dashboard.init_visualization_data()
                    new_df = dashboard.PAPERS_DF
                    new_keywords = dashboard.ALL_KEYWORDS
                    return (
                        f"已加载 **{len(new_df)}** 篇论文。",
                        gr.update(choices=new_keywords)
                    )

                refresh_dashboard_btn.click(
                    fn=refresh_dashboard_data,
                    outputs=[status_text, keyword_selector]
                )
        
        def save_prompt(prompt_text, prompt_type):
            """保存单个提示词到配置"""
            full_config = config_manager._config_data
            if "filtering" not in full_config:
                full_config["filtering"] = {}
            if "ai_screener" not in full_config["filtering"]:
                full_config["filtering"]["ai_screener"] = {}
            
            full_config["filtering"]["ai_screener"][prompt_type] = prompt_text
            
            if config_manager.save_config(full_config):
                return f"{prompt_type} 已成功保存！"
            else:
                return "提示词保存失败。"

        save_coarse_prompt_btn.click(
            lambda x: save_prompt(x, "coarse_prompt"),
            inputs=[coarse_prompt],
            outputs=[config_status]
        )
        
        save_fine_prompt_btn.click(
            lambda x: save_prompt(x, "fine_prompt"),
            inputs=[fine_prompt],
            outputs=[config_status]
        )

        def toggle_query_mode(mode):
            is_simple = mode == "简单模式"
            return gr.update(visible=is_simple), gr.update(visible=not is_simple)

        query_mode_selector.change(
            fn=toggle_query_mode,
            inputs=[query_mode_selector],
            outputs=[simple_query_group, advanced_query_group]
        )

        def validate_query(query):
            if not query:
                return "错误: 查询不能为空。"
            try:
                translated = translate_simplified_query(query)
                return f"✅ 验证通过\n转换结果: {translated}"
            except ValueError as e:
                return f"❌ 验证失败: {e}"

        validate_query_btn.click(
            fn=validate_query,
            inputs=[advanced_query_input],
            outputs=[query_validation_status]
        )

        def save_all_configs(
            source_sel, conf_names, conf_path,
            # AI Screener configs
            api_key, base_url, model, rounds, max_concurrent,
            # Crawler configs
            crawl_mode, start_date, end_date,
            query_mode, keywords_must, keywords_optional, advanced_query,
            max_results, base_delay, max_retries, check_hour,
            http_proxy, https_proxy
        ):
            full_config = config_manager._config_data

            # === 1. 保存 AI 筛选器 ===
            ai_cfg = full_config.setdefault("filtering", {}).setdefault("ai_screener", {})
            ai_cfg.update({
                "api_key": api_key,
                "base_url": base_url,
                "model": model,
                "rounds": rounds,
                "max_concurrent": max_concurrent
            })

            # === 2. 构建 crawler 配置基础结构（所有模式通用） ===
            crawler_dict = {
                "source": source_sel,   # ← 关键：保存当前模式：arxiv 或 conference
                "query_mode": "simple" if query_mode == "简单模式" else "advanced",
                "advanced_query": advanced_query,
                "keywords": {
                    "must": [kw.strip() for kw in keywords_must.split(",") if kw.strip()],
                    "optional": [kw.strip() for kw in keywords_optional.split(",") if kw.strip()]
                },
                "proxy": {
                    "http": http_proxy or None,
                    "https": https_proxy or None
                },
                "paths": full_config.get("crawler", {}).get("paths", {
                    "base_dir": "arxiv_papers",
                    "log_file": "arxiv_crawler.log"
                })
            }

            # === 3. 如果是 conference 模式，写入 conference_params ===
            if source_sel == "conference":
                crawler_dict["conference_params"] = {
                    "source_path": conf_path,
                    "names": [n.strip() for n in conf_names.split(",") if n.strip()]
                }

            # === 4. 只有 arxiv 模式才写入 date_range / arxiv_params / crawl_mode ===
            if source_sel == "arxiv":
                crawler_dict.update({
                    "crawl_mode": crawl_mode,
                    "date_range": {
                        "start_date": start_date,
                        "end_date": end_date
                    },
                    "arxiv_params": {
                        "max_results_per_request": max_results,
                        "base_delay": base_delay,
                        "max_retries": max_retries,
                        "incremental_check_hour": check_hour
                    }
                })

            full_config["crawler"] = crawler_dict

            if config_manager.save_config(full_config):
                return "所有配置已成功保存！"
            else:
                return "配置保存失败，请检查日志。"

        save_config_btn.click(
            save_all_configs,
            inputs=[
                source_selector,              # ← 新增
                conference_names_input,       # ← 新增
                conference_path_input,        # ← 新增

                api_key_input, base_url_input, model_input, rounds_input, max_concurrent_input,
                crawl_mode_input, start_date_cfg, end_date_cfg,
                query_mode_selector, keywords_must_input, keywords_optional_input, advanced_query_input,
                max_results_input, base_delay_input, max_retries_input, check_hour_input,
                http_proxy_input, https_proxy_input
            ],
            outputs=config_status
        )

        def refresh_files():
            input_files = get_json_files()
            result_files = get_result_files()
            return (
                gr.update(choices=input_files), 
                gr.update(choices=[""] + input_files), 
                gr.update(choices=result_files)
            )
        
        refresh_files_btn.click(
            refresh_files,
            outputs=[main_file_dropdown, findings_file_dropdown, input_file_dropdown]
        )
        refresh_input_files_btn.click(
            refresh_files,
            outputs=[main_file_dropdown, findings_file_dropdown, input_file_dropdown]
        )

    return app
