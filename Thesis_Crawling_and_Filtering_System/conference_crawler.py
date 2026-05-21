#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unified_conference_entry.py

统一入口：
    python unified_conference_entry.py --conf AAAI-2025
    python unified_conference_entry.py --conf CVPR-2025
    python unified_conference_entry.py --conf ACMMM-2024
    python unified_conference_entry.py --conf NeurIPS-2025
    python unified_conference_entry.py --conf ICML-2025
    python unified_conference_entry.py --conf ACL-2025

说明：
- 不修改各爬虫文件的内部逻辑，只做薄封装。
- 统一输出字段：title, authors, abstract, url, venue
- venue 规则：
    * 如果原始数据中包含 track 信息（oral/poster/spotlight），则标为
      如：ACMMM-2025-oral, NeurIPS-2025-poster 等（小写后缀）。
    * 否则标为：AAAI-2025, CVPR-2025, ACL-2025 等。
"""

import argparse
import json
import re
import os
from typing import List, Dict, Any

# 各爬虫
from src.crawler.aaai import AAAISpider
from src.crawler.cvf import CVFSpider
from src.crawler.acmmm import ACMMMSpider
from src.crawler.acmmm_2025 import ACMMM25Spider

# NeurIPS / ICML 使用现有 conference_crawler 的逻辑
from src.crawler.openreview import OpenreviewCrawler

# ACL 爬虫（如果你已经写好 ACLSpider，就正常导入；否则 ACL 相关功能会报错提示）
from src.crawler.acl import ACLSpider  # type: ignore



# ============================================================
# 工具函数
# ============================================================

def parse_conf_token(token: str):
    """
    把 AAAI-2025 / cvpr2024 / NeurIPS2025 之类解析成 (name, year)
    返回：(NAME大写, year int)
    """
    s = token.strip()
    m = re.fullmatch(r'([A-Za-z]+)[\-_]?(\d{4})', s)
    if not m:
        raise ValueError(f"无法解析 conf 标记: {token!r}，建议形如 AAAI-2025")

    name_raw = m.group(1)
    year = int(m.group(2))
    name_upper = name_raw.upper()
    return name_upper, year


def normalize_authors(auth_val):
    """
    统一 authors 字段为 List[str]
    - 如果已经是 list，直接返回
    - 如果是字符串，用 , 或 ; 切分
    - 否则包装成单元素 list
    """
    if isinstance(auth_val, list):
        return auth_val
    if isinstance(auth_val, str):
        parts = re.split(r'[;,]', auth_val)
        return [p.strip() for p in parts if p.strip()]
    if auth_val is None:
        return []
    return [str(auth_val)]


def normalize_item(
    item: Dict[str, Any],
    venue_value: str,
) -> Dict[str, Any]:
    """
    统一每篇论文的字段：
    - title
    - authors (List[str])
    - abstract
    - url
    - venue
    """

    title = item.get("title") or ""
    abstract = item.get("abstract") or ""
    # url 字段有时叫 pdf_url
    url = item.get("url") or item.get("pdf_url") or ""

    authors = normalize_authors(item.get("authors"))

    return {
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "url": url,
        "venue": venue_value,
    }


# ============================================================
# 各会议封装
# ============================================================

def run_aaai(year: int, proxy: str = None) -> List[Dict[str, Any]]:
    """
    使用现有 AAAISpider，逻辑不改，只在外面做字段统一。
    """
    # 你可以传 "AAAI2024" / "2024" / "AAAI-24" 都行，这里直接用年份字符串
    spider = AAAISpider(str(year), proxy=proxy)
    raw_list = spider.crawl()
    venue_tag = f"AAAI-{year}"

    return [
        normalize_item(p, venue_tag)
        for p in raw_list
    ]


def run_cvf(short_name: str, year: int, proxy: str = None) -> List[Dict[str, Any]]:
    """
    CVPR / ICCV / WACV 等 CVF 系列
    例如：CVPR-2025 -> conference="CVPR2025"
    """
    conference_code = f"{short_name}{year}"
    spider = CVFSpider(conference=conference_code, proxy=proxy, workers=10)
    raw_list = spider.crawl_all()
    venue_tag = f"{short_name}-{year}"

    return [
        normalize_item(p, venue_tag)
        for p in raw_list
    ]


def run_acmmm(year: int, proxy: str = None) -> List[Dict[str, Any]]:
    """
    统一处理 ACMMM 2025(纯 list) 和 其他年份(oral/poster dict)
    """

    # --- step 1: 获取 data ---
    if year == 2025:
        spider = ACMMM25Spider(year=str(year), proxy=proxy)
        data = spider.crawl_all()            # <-- list
    else:
        spider = ACMMMSpider(year=str(year), proxy=proxy)
        data = spider.crawl()                # <-- dict

    merged: List[Dict[str, Any]] = []

    # --- step 2: 如果 data 是 dict（oral/poster 分 track） ---
    if isinstance(data, dict):
        for tag in ("oral", "poster"):
            papers = data.get(tag, []) or []
            for p in papers:
                venue = f"ACMMM-{year}-{tag}"
                merged.append(normalize_item(p, venue))

        # dict 且拿到 papers：直接返回
        if merged:
            return merged

        # dict 但为空：兜底
        return []

    # --- step 3: 如果 data 是 list（2025 年） ---
    elif isinstance(data, list):
        return [
            normalize_item(p, f"ACMMM-{year}")
            for p in data
        ]

    # --- 兜底 ---
    return []

def run_neurips_or_icml(name: str, year: int, proxy: str = None) -> List[Dict[str, Any]]:
    """
    使用新版 ConferenceCrawler class（自动生成 invitation）
    不再依赖 SUBMISSION_INV 字典
    不再手动 fetch / parse，由类内部完成
    """
    conf_key = f"{name.capitalize().upper()}{year}"  # NeurIPS2025 / ICML2025

    # 创建 crawler（支持 proxy）
    crawler = OpenreviewCrawler(conf_name=conf_key, proxy=proxy)

    # 运行爬虫（返回 oral / poster / spotlight）
    raw_items = crawler.crawl()

    results = []

    # 对每条记录统一规范字段 & 生成 venue
    for item in raw_items:
        venue_lower = item.get("venue", "").lower()

        if "oral" in venue_lower:
            suffix = "oral"
        elif "poster" in venue_lower:
            suffix = "poster"
        elif "spotlight" in venue_lower:
            suffix = "spotlight"
        else:
            suffix = ""

        venue_tag = f"{name.upper()}-{year}"
        if suffix:
            venue_tag = f"{venue_tag}-{suffix}"

        results.append(normalize_item(item, venue_tag))

    return results


def run_acl(year: int, proxy: str = None) -> List[Dict[str, Any]]:
    """
    ACL 入口。
    - 如果你已经在 acl.py 里实现了 ACLSpider(year, proxy).crawl()，这里直接调用。
    - 如果还没实现，调用时会抛出清晰的异常。
    """
    if ACLSpider is None:
        raise RuntimeError(
            "当前 acl.py 中没有定义 ACLSpider，或导入失败。\n"
            "请先在 acl.py 中实现 ACLSpider(year, proxy).crawl()，"
            "然后再使用 ACL-xxxx 选项。"
        )

    spider = ACLSpider(year=str(year), proxy=proxy)
    raw_list = spider.crawl()
    venue_tag = f"ACL-{year}"

    # raw_list 可以是 list[dict]，也可以是带 track 的结构，这里假设为 list[dict]
    return [normalize_item(p, venue_tag) for p in raw_list]


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--conf", type=str, required=True)
    parser.add_argument("--proxy", type=str, required=True)

    # ⭐ 新增 outdir 参数，默认 ./conference_papers/
    parser.add_argument(
        "--outdir",
        type=str,
        default="./conference_papers/",
        help="保存 JSON 文件的目录（默认 ./conference_papers/）"
    )

    args = parser.parse_args()
    name_upper, year = parse_conf_token(args.conf)

    proxy = args.proxy
    outdir = args.outdir

    # 目录不存在则创建
    os.makedirs(outdir, exist_ok=True)

    # 路由逻辑（不改）
    if name_upper == "AAAI":
        data = run_aaai(year, proxy=proxy)
    elif name_upper in {"CVPR", "ICCV", "ECCV"}:
        data = run_cvf(name_upper, year, proxy=proxy)
    elif name_upper == "ACMMM":
        print(year)
        data = run_acmmm(year, proxy=proxy)
    elif name_upper in {"NEURIPS", "ICML", "ICLR"}:
        data = run_neurips_or_icml(name_upper.capitalize(), year, proxy=proxy)
    elif name_upper == "ACL":
        data = run_acl(year, proxy=proxy)
    else:
        raise ValueError(f"暂不支持的会议前缀: {name_upper}")

    # ⭐ 输出路径放入 outdir 里
    out_path = os.path.join(outdir, f"{name_upper}_{year}.json")

    output_data = {"papers": data}

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已写出标准化 JSON: {out_path}")
    print(f"   共 {len(output_data)} 篇论文")


if __name__ == "__main__":
    main()

""" 
python conference_crawler.py \
    --conf CVPR-2026 \
    --proxy http://127.0.0.1:19023 \
    --outdir ./conference_papers/ 
"""
