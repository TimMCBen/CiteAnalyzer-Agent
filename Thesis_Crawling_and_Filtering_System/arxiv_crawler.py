# -*- coding: utf-8 -*-
"""
arXiv 论文爬虫主入口文件。

该脚本负责：
1. 初始化配置模块，从 `config.json` 加载设置。
2. 设置日志、代理和数据目录。
3. 根据配置中的 `crawl_mode` 决定执行哪种爬取模式：
   - `date_range`: 执行一次性范围爬取。
   - `incremental`: 启动持续运行的增量爬取和定时任务。
"""

import logging
import os
from datetime import datetime, timezone

from src.config_manager import config_manager
from src.utils import ensure_directories, GradioLogHandler
from src.crawler.modes import crawl_by_date_range, run_incremental_mode, crawl_conference

def setup_logging(log_file: str, use_gradio_handler: bool = False):
    """根据配置设置日志记录器"""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    handlers = [
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
    
    if use_gradio_handler:
        gradio_handler = GradioLogHandler()
        gradio_handler.setLevel(logging.INFO)
        gradio_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        handlers.append(gradio_handler)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    logging.info("日志系统已配置。")

def set_proxy(proxy_config: dict):
    """根据配置设置代理环境变量"""
    http_proxy = proxy_config.get("http")
    https_proxy = proxy_config.get("https")
    if http_proxy:
        os.environ["HTTP_PROXY"] = http_proxy
        logging.info(f"已设置 HTTP_PROXY: {http_proxy}")
    if https_proxy:
        os.environ["HTTPS_PROXY"] = https_proxy
        logging.info(f"已设置 HTTPS_PROXY: {https_proxy}")

def run_crawler_logic():
    """
    包含核心爬虫逻辑的函数，不包括日志设置。
    """
    # 1. 加载配置
    crawler_config = config_manager.get_config("crawler")
    if not crawler_config:
        logging.error("在 config.json 中未找到 'crawler' 配置，程序无法启动。")
        return

    # 2. 确保目录和代理设置
    ensure_directories(crawler_config)
    proxy_config = crawler_config.get("proxy", {})
    set_proxy(proxy_config)
    
    crawl_mode = crawler_config.get("crawl_mode", "conference")
    logging.info(f"=== 启动论文爬取系统 (模式: {crawl_mode}) ===")
    
    # 3. 根据模式选择执行路径
    if crawl_mode == "date_range":
        crawl_by_date_range(crawler_config)
    elif crawl_mode == "incremental":
        run_incremental_mode(crawler_config)
    else:
        crawl_conference(crawler_config)

def main():
    """
    程序主函数，用于独立运行爬虫。
    """
    crawler_config = config_manager.get_config("crawler")
    if not crawler_config:
        # 使用 print 因为此时日志可能还未配置
        print("错误: 在 config.json 中未找到 'crawler' 配置。")
        return
        
    paths_config = crawler_config.get("paths", {})
    log_file = paths_config.get("log_file", "arxiv_crawler.log")
    setup_logging(log_file)
    
    run_crawler_logic()

if __name__ == "__main__":
    main()
