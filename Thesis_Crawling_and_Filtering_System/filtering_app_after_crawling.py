import os
import logging
from src.visualization import dashboard
from src.filtering.ui import create_interface
from arxiv_crawler import setup_logging
from src.config_manager import config_manager

def main():
    # --- 日志配置 ---
    crawler_config = config_manager.get_config("crawler")
    log_file = crawler_config.get("paths", {}).get("log_file", "arxiv_crawler.log")
    setup_logging(log_file, use_gradio_handler=True)
    """主函数：初始化并启动应用。"""
    # 确保数据目录存在
    if not os.path.exists("arxiv_papers"):
        os.makedirs("arxiv_papers")

    # 为可视化看板加载初始数据
    dashboard.init_visualization_data()
    
    # 创建并启动Gradio界面
    app = create_interface(dashboard.PAPERS_DF, dashboard.ALL_KEYWORDS)
    app.launch(
        server_name="0.0.0.0",
        server_port=5611,
        share=False,
        show_error=True,
        enable_queue=True
    )

if __name__ == "__main__":
    main()
