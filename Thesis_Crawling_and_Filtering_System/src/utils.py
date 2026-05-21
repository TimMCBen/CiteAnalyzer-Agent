# -*- coding: utf-8 -*-
"""
该模块提供项目所需的各种辅助工具函数。

功能包括：
- 目录和文件的初始化与管理。
- 记录失败的爬取任务。
- 管理上次爬取的时间戳。
- 论文数据的格式化与保存。
- 时间范围的处理。
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any
import pytz

# --- 全局变量 ---
BEIJING_TZ = pytz.timezone('Asia/Shanghai')
GRADIO_LOG_MESSAGES = []

# --- 日志处理 ---

class GradioLogHandler(logging.Handler):
    """一个将日志记录发送到全局列表的处理器，用于Gradio界面显示。"""
    def emit(self, record):
        log_entry = self.format(record)
        GRADIO_LOG_MESSAGES.append(log_entry)

def get_gradio_logs():
    """获取并清空当前的Gradio日志消息列表。"""
    logs = list(GRADIO_LOG_MESSAGES)
    GRADIO_LOG_MESSAGES.clear()
    return "\n".join(logs)

def clear_gradio_logs():
    """清空Gradio日志消息列表。"""
    GRADIO_LOG_MESSAGES.clear()

# --- 目录与文件管理 ---

def ensure_directories(crawler_config: Dict[str, Any]):
    """确保所有需要的目录和文件都存在"""
    paths_config = crawler_config.get("paths", {})
    base_dir = Path(paths_config.get("base_dir", "arxiv_papers"))
    failed_intervals_path = base_dir / "failed_intervals.json"
    
    base_dir.mkdir(parents=True, exist_ok=True)
    if not failed_intervals_path.exists():
        with open(failed_intervals_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
    logging.info(f"数据目录 '{base_dir}' 已确认存在。")

def get_crawler_paths(crawler_config: Dict[str, Any]) -> (Path, Path, Path):
    """从配置中获取并构造爬虫所需的路径"""
    paths_config = crawler_config.get("paths", {})
    base_dir = Path(paths_config.get("base_dir", "arxiv_papers"))
    last_crawl_time_path = base_dir / "last_crawl_time.json"
    failed_intervals_path = base_dir / "failed_intervals.json"
    return base_dir, last_crawl_time_path, failed_intervals_path

def save_failed_interval(start: datetime, end: datetime, error: Exception, crawler_config: Dict[str, Any]):
    """将失败的爬取时间区间和错误信息记录到文件"""
    _, _, failed_intervals_path = get_crawler_paths(crawler_config)
    failed = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "error": str(error),
        "record_time": datetime.now(timezone.utc).isoformat()
    }
    try:
        with open(failed_intervals_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = []
    data.append(failed)
    with open(failed_intervals_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logging.warning(f"已记录失败区间: {start.date()} 至 {end.date()}")

def save_last_crawl_time(crawl_time: datetime, crawler_config: Dict[str, Any]):
    """保存最后一次成功爬取的时间戳"""
    _, last_crawl_time_path, _ = get_crawler_paths(crawler_config)
    if crawl_time.tzinfo is None:
        crawl_time = crawl_time.astimezone(timezone.utc)
    with open(last_crawl_time_path, 'w', encoding='utf-8') as f:
        json.dump({"last_crawl": crawl_time.isoformat()}, f)

def load_last_crawl_time(crawler_config: Dict[str, Any]) -> datetime:
    """加载上次爬取的时间戳，如果文件不存在或损坏则返回当前日期"""
    _, last_crawl_time_path, _ = get_crawler_paths(crawler_config)
    if last_crawl_time_path.exists():
        try:
            with open(last_crawl_time_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return datetime.fromisoformat(data["last_crawl"])
        except (json.JSONDecodeError, KeyError):
            logging.warning("上次爬取时间文件损坏，将使用今天的日期作为起点。")
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

# --- 数据处理与保存 ---

def format_paper_data(result):
    """将从arxiv库获取的原始论文数据格式化为所需的字典结构"""
    return {
        "title": result.title.strip(),
        "abstract": result.summary.strip(),
        "authors": [author.name for author in result.authors],
        "published": result.published.astimezone(BEIJING_TZ).isoformat(),
        "updated": result.updated.astimezone(BEIJING_TZ).isoformat(),
        "arxiv_id": result.entry_id.split('/')[-1],
        "url": result.pdf_url,
        "categories": result.categories,
        "primary_category": result.primary_category,
        "matched_keywords": []
    }

def format_openreview_paper_data(submission: Dict[str, Any]) -> Dict[str, Any]:
    """
    将从 OpenReview API 获取的 submission 字典格式化为标准字典格式。
    """
    content = submission.get('content', {})
    
    # 提取标题
    title_data = content.get("title", {})
    title = title_data.get('value', '') if isinstance(title_data, dict) else str(title_data or '')

    # 提取摘要
    abstract_data = content.get("abstract", {})
    abstract = abstract_data.get('value', '') if isinstance(abstract_data, dict) else str(abstract_data or '')

    # 提取作者
    authors_data = content.get("authors", [])
    authors = []
    if isinstance(authors_data, list) and authors_data:
        # 检查列表中的第一个元素来判断结构
        if isinstance(authors_data[0], dict) and 'value' in authors_data[0]:
            authors = [author.get('value', '') for author in authors_data]
        else: # 假设是字符串列表
            authors = [str(author) for author in authors_data]

    # 提取发表和更新日期 (时间戳是毫秒)
    published_timestamp = submission.get('cdate')
    updated_timestamp = submission.get('mdate')
    
    published_date = datetime.fromtimestamp(published_timestamp / 1000, tz=BEIJING_TZ).isoformat() if published_timestamp else None
    updated_date = datetime.fromtimestamp(updated_timestamp / 1000, tz=BEIJING_TZ).isoformat() if updated_timestamp else published_date

    # 提取 URL
    pdf_url = f"https://openreview.net/pdf?id={submission.get('id')}"

    return {
        "title": title.strip(),
        "abstract": abstract.strip(),
        "authors": authors,
        "published": published_date,
        "updated": updated_date,
        "arxiv_id": submission.get('id'), # 使用 OpenReview ID 作为唯一标识
        "url": pdf_url,
        "categories": content.get("keywords", {}).get("value", []), # 使用 keywords 作为 categories
        "primary_category": None, # OpenReview 没有主分类
        "matched_keywords": []
    }

def get_file_path_for_date(publish_date: datetime, crawler_config: Dict[str, Any]) -> Path:
    """根据论文发布日期生成对应的JSON文件路径"""
    base_dir, _, _ = get_crawler_paths(crawler_config)
    year = publish_date.year
    month = publish_date.month
    return base_dir / f"arxiv_{year}_{month:02d}_llm_papers.json"

def add_new_papers(new_papers: list, crawler_config: Dict[str, Any]):
    """
    将新爬取的论文添加到对应的文件中。
    """
    papers_by_file = {}
    for paper in new_papers:
        publish_date = datetime.fromisoformat(paper['published'])
        file_path = get_file_path_for_date(publish_date, crawler_config)
        if file_path not in papers_by_file:
            papers_by_file[file_path] = []
        papers_by_file[file_path].append(paper)

    for file_path, papers in papers_by_file.items():
        existing_papers = []
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content:
                        existing_papers = json.loads(content).get('papers', [])
            except json.JSONDecodeError:
                logging.warning(f"文件 {file_path} 格式错误，将覆盖。")

        existing_papers_map = {p['arxiv_id']: p for p in existing_papers}
        updated_papers = []
        newly_added_count = 0
        updated_count = 0

        for new_paper in papers:
            arxiv_id = new_paper['arxiv_id']
            if arxiv_id in existing_papers_map:
                # 论文已存在，检查是否需要更新
                old_paper = existing_papers_map[arxiv_id]
                # 比较关键字段，例如 matched_keywords
                if sorted(new_paper.get('matched_keywords', [])) != sorted(old_paper.get('matched_keywords', [])):
                    # 关键词不同，更新论文
                    updated_papers.append(new_paper)
                    updated_count += 1
                    logging.debug(f"更新论文: {arxiv_id} (关键词变化)")
                else:
                    # 关键词相同，保留旧论文（或新论文，这里选择保留旧论文以避免不必要的写入）
                    updated_papers.append(old_paper)
            else:
                # 新论文
                updated_papers.append(new_paper)
                newly_added_count += 1
                logging.debug(f"新增论文: {arxiv_id}")
        
        # 将未被新爬取数据覆盖的旧论文也加回来
        for arxiv_id, old_paper in existing_papers_map.items():
            if arxiv_id not in {p['arxiv_id'] for p in updated_papers}:
                updated_papers.append(old_paper)

        if newly_added_count > 0 or updated_count > 0:
            save_papers_to_file(updated_papers, file_path, crawler_config)
            logging.info(f"文件 {file_path} 已更新: 新增 {newly_added_count} 篇，更新 {updated_count} 篇。")
        else:
            logging.info(f"文件 {file_path} 没有新的或更新的论文需要处理。")

def save_papers_to_file(papers: list, file_path: Path, crawler_config: Dict[str, Any]):
    """将论文列表保存到指定的JSON文件，并包含元数据"""
    sorted_papers = sorted(papers, key=lambda x: x['published'], reverse=True)
    
    keyword_stats = {}
    for paper in sorted_papers:
        for kw in paper.get("matched_keywords", []):
            keyword_stats[kw] = keyword_stats.get(kw, 0) + 1

    data = {
        "metadata": {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "total_papers": len(sorted_papers),
            "matched_keywords_stats": keyword_stats
        },
        "papers": sorted_papers
    }
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logging.info(f"已保存 {len(sorted_papers)} 篇论文到 {file_path}")

# --- 时间处理 ---

def split_time_range_by_day(start, end):
    """
    将一个时间范围按天拆分成多个小的24小时范围。
    例如：(2024-01-01, 2024-01-03) -> [(2024-01-01, ...), (2024-01-02, ...)]
    """
    ranges = []
    current = start
    while current.date() <= end.date():
        # 每天的范围是 [当天00:00:00, 当天23:59:59.999999]
        day_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1) - timedelta(microseconds=1)
        ranges.append((day_start, day_end))
        current += timedelta(days=1)
    return ranges
