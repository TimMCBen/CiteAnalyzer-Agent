# -*- coding: utf-8 -*-
"""
该模块实现了爬虫的两种主要操作模式。

- `crawl_by_date_range`: 根据配置中定义的日期范围执行一次性爬取。
- `run_incremental_mode`: 运行增量爬取模式，该模式会持续运行，
  自动追赶错过的日期，并按计划执行每日的定时爬取任务。
"""

import logging
import time
from datetime import datetime, timedelta, timezone
import schedule

from typing import Dict, Any

from .core import search_papers
from ..utils import (
    add_new_papers,
    load_last_crawl_time,
    save_last_crawl_time,
    split_time_range_by_day,
    save_failed_interval
)

def crawl_conference(crawler_config: Dict[str, Any]):
    """
    根据配置执行一次性范围爬取。
    """
    logging.info("--- 本地会议模式爬取 ---")
    
    total_papers_found = 0
    source = crawler_config.get("source", "arxiv").lower()

    if source == "conference":
        logging.info("conference 源模式，将执行单次数据获取。")
        try:
            papers = search_papers(None, None, crawler_config)
            if papers:
                total_papers_found = len(papers)
                add_new_papers(papers, crawler_config)
        except Exception as e:
            logging.error(f"conference 爬取失败: {e}")
    else:
        logging.error(f"不支持的数据源: {source}")

    logging.info(f"--- 本地会议模式爬取完成 ---")
    logging.info(f"在本次任务中，总共爬取了 {total_papers_found} 篇论文。")


def crawl_by_date_range(crawler_config: Dict[str, Any]):
    """
    根据配置执行一次性范围爬取。
    """
    logging.info("--- 开始按日期范围模式爬取 ---")
    
    total_papers_found = 0
    source = crawler_config.get("source", "arxiv").lower()

    if source == "conference":
        logging.info("conference 源模式，将执行单次数据获取。")
        try:
            papers = search_papers(None, None, crawler_config)
            if papers:
                total_papers_found = len(papers)
                add_new_papers(papers, crawler_config)
        except Exception as e:
            logging.error(f"conference 爬取失败: {e}")
    
    elif source == "arxiv":
        date_range_config = crawler_config.get("date_range", {})
        start_date_str = date_range_config.get("start_date")
        end_date_str = date_range_config.get("end_date")

        if not start_date_str or not end_date_str:
            logging.error("在 config.json 中未找到有效的 'date_range' 配置。")
            return

        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        
        logging.info(f"时间范围: {start_date.date()} to {end_date.date()}")
        
        time_ranges = split_time_range_by_day(start_date, end_date)
        total_ranges = len(time_ranges)
        
        for i, (start, end) in enumerate(time_ranges):
            logging.info(f"处理第 {i+1}/{total_ranges} 个区间: {start.date()}")
            try:
                papers = search_papers(start, end, crawler_config)
                if papers:
                    num_found = len(papers)
                    total_papers_found += num_found
                    add_new_papers(papers, crawler_config)
            except Exception as e:
                logging.error(f"区间 {start.date()} 爬取失败: {e}")
                save_failed_interval(start, end, e, crawler_config)
    
    else:
        logging.error(f"不支持的数据源: {source}")

    logging.info(f"--- 日期范围模式爬取完成 ---")
    logging.info(f"在本次任务中，总共爬取了 {total_papers_found} 篇论文。")

def _incremental_crawl_task(crawler_config: Dict[str, Any]):
    """
    内部函数，执行单次增量爬取任务。
    """
    source = crawler_config.get("source", "arxiv").lower()
    if source == "openreview":
        logging.info("OpenReview 源不支持增量模式，跳过本次任务。")
        return

    last_run_time = load_last_crawl_time(crawler_config)
    current_time = datetime.now(timezone.utc)
    
    if (current_time - last_run_time) < timedelta(hours=1):
        logging.info("距离上次成功记录不足1小时，跳过本次增量爬取。")
        return

    arxiv_params = crawler_config.get("arxiv_params", {})
    check_hour = arxiv_params.get("incremental_check_hour", 12)

    today_at_crawl_hour = current_time.replace(hour=check_hour, minute=0, second=0, microsecond=0)
    delayed_window_start = today_at_crawl_hour - timedelta(days=4)
    delayed_window_end = today_at_crawl_hour - timedelta(days=3)

    last_crawled_window_end = (last_run_time.replace(hour=check_hour, minute=0, second=0, microsecond=0) - timedelta(days=3))
    
    if last_crawled_window_end < delayed_window_start:
        logging.info(f"检测到数据空缺，开始追赶爬取: {last_crawled_window_end.date()} 至 {delayed_window_start.date()}")
        time_ranges = split_time_range_by_day(last_crawled_window_end, delayed_window_start)
        for start, end in time_ranges:
            papers = search_papers(start, end, crawler_config)
            if papers:
                add_new_papers(papers, crawler_config)
        logging.info("追赶爬取完成。")

    logging.info(f"开始常规延时增量爬取: {delayed_window_start.date()} 至 {delayed_window_end.date()}")
    papers = search_papers(delayed_window_start, delayed_window_end, crawler_config)
    if papers:
        add_new_papers(papers, crawler_config)
    
    save_last_crawl_time(current_time, crawler_config)
    logging.info("增量爬取任务完成。")

def run_incremental_mode(crawler_config: Dict[str, Any]):
    """
    运行增量模式。
    """
    logging.info("--- 开始增量模式 ---")
    
    last_run = load_last_crawl_time(crawler_config)
    if (datetime.now(timezone.utc) - last_run) > timedelta(hours=23):
        logging.info("检测到自上次运行以来已超过23小时，立即执行一次增量任务以追赶数据...")
        try:
            _incremental_crawl_task(crawler_config)
        except Exception as e:
            logging.error(f"启动时的追赶任务失败: {e}")

    arxiv_params = crawler_config.get("arxiv_params", {})
    check_hour = arxiv_params.get("incremental_check_hour", 12)
    
    schedule.every().day.at(f"{check_hour:02}:00").do(_incremental_crawl_task, crawler_config=crawler_config)
    logging.info(f"已设置定时任务：每天 {check_hour:02}:00 执行。")
    
    logging.info("开始运行定时任务调度器...")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logging.info("用户中断，程序退出。")
    except Exception as e:
        logging.error(f"调度器发生未知错误: {e}，程序退出。")
