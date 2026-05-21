# -*- coding: utf-8 -*-
"""
该模块包含爬虫的核心功能。

主要负责：
- 根据配置选择数据源（如 arXiv、OpenReview）。
- 为 arXiv 构建 API 查询。
- 连接 API 或读取本地数据，获取论文。
- 格式化和返回论文数据。
"""

import logging
import arxiv
import openreview
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from src.utils import format_paper_data, format_openreview_paper_data, save_failed_interval
from .query_translator import parse_advanced_query, extract_keywords_from_config

def search_papers(start_date: Optional[datetime], end_date: Optional[datetime], crawler_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    根据配置选择数据源并执行搜索。
    """
    source = crawler_config.get("source", "arxiv").lower()
    logging.info(f"选择的数据源: {source}")

    if source == "arxiv":
        if not start_date or not end_date:
            logging.error("arXiv 源需要提供 start_date 和 end_date。")
            return []
        return search_arxiv_papers(start_date, end_date, crawler_config)
    elif source == "conference":
        return search_conference_papers(crawler_config)
    else:
        logging.error(f"不支持的数据源: {source}")
        return []

def search_conference_papers(crawler_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    从本地 source_path 加载会议数据（可多个），按关键词过滤。
    支持 simple / advanced 两种查询模式。
    """
    print("开始搜索会议论文...")
    # ----------------------------
    # 读取配置
    # ----------------------------
    conf_cfg = crawler_config.get("conference_params", {})
    source_path = conf_cfg.get("source_path")
    names = conf_cfg.get("names")

    if not source_path or not names:
        logging.error("conference_params 必须包含 source_path 和 names 字段。")
        return []

    if isinstance(names, str):
        names = [names]
    elif not isinstance(names, list):
        logging.error("conference_params.names 必须为字符串或字符串列表")
        return []

    # ----------------------------
    # 加载所有会议 JSON
    # ----------------------------
    all_papers = []

    for conf_name in names:
        normalized_name = (
            conf_name.replace("-", "_")
                     .replace(".", "_")
                     .replace("/", "_")
                     .strip()
        )

        candidate_files = [
            f"{normalized_name}.json",
            f"{normalized_name.upper()}.json",
            f"{normalized_name.lower()}.json",
            f"{conf_name}.json",
            f"{conf_name.replace('-', '_')}.json"
        ]

        json_path = None
        for fname in candidate_files:
            path = os.path.join(source_path, fname)
            if os.path.exists(path):
                json_path = path
                break

        if not json_path:
            logging.error(
                f"[{conf_name}] 没找到 JSON 文件，尝试路径如下：\n" +
                "\n".join([os.path.join(source_path, f) for f in candidate_files])
            )
            continue

        logging.info(f"[{conf_name}] 加载数据: {json_path}")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                papers = json.load(f)
        except Exception as e:
            logging.error(f"[{conf_name}] JSON 加载失败: {e}")
            continue

        for p in papers:
            p["conference"] = conf_name

        all_papers.extend(papers)

    if not all_papers:
        logging.warning("未加载到任何会议论文")
        return []

    logging.info(f"总计加载 {len(all_papers)} 篇会议论文")

    # ----------------------------
    # 构建关键词（支持 simple / advanced）
    # ----------------------------
    query_mode = crawler_config.get("query_mode", "simple")

    if query_mode == "advanced":
        simplified_query = crawler_config.get("advanced_query", "")
        if not simplified_query:
            logging.error("query_mode=advanced，但 advanced_query 为空")
            return []

        try:
            # parse_advanced_query 返回:
            #   1. API 查询字符串 (这里本地不用)
            #   2. 提取的关键词列表
            _parsed_query, extracted_keywords = parse_advanced_query(simplified_query)

            keywords_to_match = extracted_keywords

            logging.info(f"高级查询解析成功: {simplified_query}")
            logging.info(f"提取到关键词: {keywords_to_match}")

        except Exception as e:
            logging.error(f"解析高级查询失败: {e}")
            return []

    else:
        # simple 模式
        keywords_cfg = crawler_config.get("keywords", {})
        must_keywords = keywords_cfg.get("must", [])
        optional_keywords = keywords_cfg.get("optional", [])
        keywords_to_match = list(set(must_keywords + optional_keywords))

        logging.info(f"simple 模式关键词: {keywords_to_match}")

    # ----------------------------
    # 执行匹配
    # ----------------------------
    if not keywords_to_match:
        logging.info("无关键词过滤，返回全部论文")
        return [format_openreview_paper_data(p) for p in all_papers]

    matched_papers = []

    for paper in all_papers:
        pdata = format_openreview_paper_data(paper)
        pdata["conference"] = paper.get("conference", "unknown")

        text = (pdata["title"] + pdata["abstract"]).lower()

        matched = []
        for kw in keywords_to_match:
            kw_lower = kw.lower()

            if " " in kw_lower:  # phrase
                if all(token in text for token in kw_lower.split()):
                    matched.append(kw)
            else:
                if kw_lower in text:
                    matched.append(kw)

        if matched:
            pdata["matched_keywords"] = matched
            matched_papers.append(pdata)

    logging.info(f"最终匹配到 {len(matched_papers)} 篇论文")
    return matched_papers


def build_arxiv_query(start_date: datetime, end_date: datetime, crawler_config: Dict[str, Any]) -> Tuple[str, List[str]]:
    """
    根据配置构建 arXiv API 查询，并返回查询字符串和用于匹配的关键词列表。
    """
    query_mode = crawler_config.get("query_mode", "simple")
    base_query = ""
    keywords = []

    if query_mode == "advanced":
        logging.info("使用高级查询模式构建查询。")
        simplified_query = crawler_config.get("advanced_query", "")
        if not simplified_query:
            logging.warning("高级查询模式已启用，但 'advanced_query' 为空。")
            return "", []
        try:
            base_query, keywords = parse_advanced_query(simplified_query)
            logging.info(f"高级查询: '{simplified_query}'")
            logging.info(f"转换为 API 查询: '{base_query}'")
            logging.info(f"提取到关键词: {keywords}")
        except Exception as e:
            logging.error(f"高级查询解析失败: {e}")
            raise e

    else: # simple mode
        logging.info("使用简单查询模式构建查询。")
        keywords_config = crawler_config.get("keywords", {})
        keywords_must = keywords_config.get("must", [])
        keywords_optional = keywords_config.get("optional", [])
        keywords = list(set(keywords_must + keywords_optional))

        must_queries = [f'(ti:"{kw}" OR abs:"{kw}")' for kw in keywords_must]
        must_part = "(" + " OR ".join(must_queries) + ")" if must_queries else ""

        optional_queries = [f'(ti:"{kw}" OR abs:"{kw}")' for kw in keywords_optional]
        optional_part = "(" + " OR ".join(optional_queries) + ")" if optional_queries else ""
        
        query_parts = [part for part in [must_part, optional_part] if part]
        base_query = " AND ".join(query_parts)

    # 附加时间范围
    date_part = f"submittedDate:[{start_date.strftime('%Y%m%d')} TO {end_date.strftime('%Y%m%d')}]"
    
    if base_query:
        final_query = f"({base_query}) AND {date_part}"
    else:
        final_query = date_part
    
    logging.debug(f"最终构建的查询: {final_query}")
    return final_query, keywords

def search_arxiv_papers(start_date: datetime, end_date: datetime, crawler_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    在指定的时间范围内，使用构建好的查询字符串搜索 arXiv 上的论文。

    Args:
        start_date (datetime): 搜索的开始日期 (aware, UTC)。
        end_date (datetime): 搜索的结束日期 (aware, UTC)。

    Returns:
        list: 包含格式化后的论文数据的列表。
    """
    query, keywords_to_match = build_arxiv_query(start_date, end_date, crawler_config)
    if not query:
        logging.error("查询字符串为空，终止本次搜索。")
        return []
        
    logging.info(f"执行搜索: 时间范围 {start_date.date()} to {end_date.date()}")
    
    arxiv_params = crawler_config.get("arxiv_params", {})
    max_results = arxiv_params.get("max_results_per_request", 25)
    delay = arxiv_params.get("base_delay", 30)
    retries = arxiv_params.get("max_retries", 5)

    # 初始化 arxiv 客户端
    client = arxiv.Client(
        page_size=max_results,
        delay_seconds=delay,
        num_retries=retries
    )
    
    # 创建搜索对象
    search = arxiv.Search(
        query=query,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )

    logging.info(f"本次查询将使用以下关键词进行匹配: {keywords_to_match}")

    papers = []
    try:
        # 执行搜索并处理结果
        for result in client.results(search):
            paper_data = format_paper_data(result)
            
            # 使用从查询构建过程中得到的关键词列表进行检查
            matched_kws = set()
            text_to_check = (paper_data["title"] + paper_data["abstract"]).lower()
            for kw in keywords_to_match:
                kw_lower = kw.lower()
                # 如果关键词是短语（包含空格），则检查所有单词是否存在
                if ' ' in kw_lower:
                    if all(word in text_to_check for word in kw_lower.split()):
                        matched_kws.add(kw)
                # 否则，作为单个关键词检查
                elif kw_lower in text_to_check:
                    matched_kws.add(kw)
            paper_data["matched_keywords"] = list(matched_kws)
            
            papers.append(paper_data)
            if len(papers) % 50 == 0:
                logging.info(f"已找到 {len(papers)} 篇论文...")

    except Exception as e:
        logging.error(f"在时间范围 {start_date.date()} - {end_date.date()} 的搜索过程中发生错误: {e}")
        save_failed_interval(start_date, end_date, e, crawler_config)
    
    logging.info(f"在 {start_date.date()} 范围内找到 {len(papers)} 篇论文。")
    return papers
