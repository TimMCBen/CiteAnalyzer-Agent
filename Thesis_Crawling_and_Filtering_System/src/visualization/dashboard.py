import json
import logging
from pathlib import Path
import pandas as pd

# --- 全局变量 ---
PAPERS_DF = pd.DataFrame()
ALL_KEYWORDS = []

def load_all_papers_for_viz(data_dir="arxiv_papers"):
    logging.info(f"开始从 '{data_dir}' 目录为看板加载论文数据...")
    path = Path(data_dir)
    if not path.exists():
        return pd.DataFrame(), []

    all_papers = []
    json_files = [f for f in path.glob("*.json") if f.name not in ['last_crawl_time.json', 'failed_intervals.json']]

    for file in json_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "papers" in data:
                    all_papers.extend(data["papers"])
                elif "relevant_papers" in data:
                    all_papers.extend(data["relevant_papers"])
        except Exception as e:
            logging.error(f"读取文件 {file} 时发生错误: {e}")

    if not all_papers:
        return pd.DataFrame(), []

    df = pd.DataFrame(all_papers).drop_duplicates(subset=['arxiv_id']).dropna(subset=['arxiv_id', 'title'])
    df['published_dt'] = pd.to_datetime(df['published'], errors='coerce', utc=True)
    df.dropna(subset=['published_dt'], inplace=True)
    
    # 确保 'matched_keywords' 列存在，如果不存在则创建空列表
    if 'matched_keywords' not in df.columns:
        df['matched_keywords'] = [[] for _ in range(len(df))]
    
    # 提取所有关键词，并确保 kws 是一个可迭代的列表
    all_keywords = sorted(list(set(kw for kws in df['matched_keywords'].dropna() if isinstance(kws, list) for kw in kws)))
    logging.info(f"看板成功加载 {len(df)} 篇论文，提取出 {len(all_keywords)} 个唯一关键词。")
    return df, all_keywords

def filter_and_display_papers(start_date_str, end_date_str, selected_keywords):
    if PAPERS_DF.empty:
        return "没有加载到任何论文数据。"

    filtered_df = PAPERS_DF.copy()

    try:
        if start_date_str and end_date_str:
            start_dt = pd.to_datetime(start_date_str).tz_localize('UTC')
            end_dt = pd.to_datetime(end_date_str).tz_localize('UTC') + pd.Timedelta(days=1)
            filtered_df = filtered_df[(filtered_df['published_dt'] >= start_dt) & (filtered_df['published_dt'] < end_dt)]
    except Exception as e:
        logging.error(f"日期格式错误: {e}")
        return f"日期格式错误，请输入 YYYY-MM-DD 格式。错误详情: {e}"

    if selected_keywords:
        keywords_set = set(selected_keywords)
        mask = filtered_df['matched_keywords'].apply(lambda kws: keywords_set.issubset(set(kws)) if isinstance(kws, list) else False)
        filtered_df = filtered_df[mask]
        
    filtered_df = filtered_df.sort_values(by='published_dt', ascending=False)

    if filtered_df.empty:
        return "没有找到符合条件的论文。"

    output_md = f"**找到 {len(filtered_df)} 篇相关论文**\n\n---\n\n"
    for _, paper in filtered_df.iterrows():
        title = paper.get('title', 'N/A')
        arxiv_id = paper.get('arxiv_id', '')
        url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "#"
        authors = ", ".join(paper.get('authors', []))
        published_date = paper['published_dt'].strftime('%Y-%m-%d')
        abstract = paper.get('abstract', '无摘要').replace('\n', ' ')
        
        # 确保 matched_keywords 是一个列表
        keywords_list = paper.get('matched_keywords', [])
        if not isinstance(keywords_list, list):
            keywords_list = []
        keywords_tags = " ".join([f"`{kw}`" for kw in keywords_list])

        output_md += (
            f"### 📄 [{title}]({url})\n\n"
            f"**作者**: {authors}\n\n"
            f"**发表日期**: {published_date}\n\n"
            f"**关键词**: {keywords_tags}\n\n"
            f"<details><summary>摘要</summary><p>{abstract}</p></details>\n\n"
            "---\n\n"
        )
    return output_md

def init_visualization_data():
    """初始化可视化数据"""
    global PAPERS_DF, ALL_KEYWORDS
    PAPERS_DF, ALL_KEYWORDS = load_all_papers_for_viz()
