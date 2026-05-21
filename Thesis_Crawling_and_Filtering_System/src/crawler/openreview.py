#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import argparse
import json
import time
from pathlib import Path
from urllib3.exceptions import IncompleteRead
from requests.exceptions import ChunkedEncodingError
import openreview


class OpenreviewCrawler:
    """
    支持任意年份 NeurIPSxxxx / ICMLxxxx 自动生成 invitation
    不再依赖 SUBMISSION_INV 字典
    """

    BASEURL = "https://api2.openreview.net"

    def __init__(self, conf_name: str, proxy: str = None):
        """
        conf_name: e.g. 'NeurIPS2025', 'ICML2024'
        proxy:     e.g. 'http://10.104.5.51:7897'
        """

        self.conf_name = conf_name
        self.proxy = proxy
        # --------------------------
        # 解析会议名 + 年份（关键步骤）
        # --------------------------
        self.venue, self.year = self.parse_conf(conf_name)

        # --------------------------
        # 自动生成 invitation
        # --------------------------
        self.inv = self.make_invitation(self.venue, self.year)

        # --------------------------
        # 设置代理
        # --------------------------
        if proxy:
            os.environ["http_proxy"] = proxy
            os.environ["https_proxy"] = proxy

        # OpenReview 客户端
        self.client = openreview.api.OpenReviewClient(baseurl=self.BASEURL)

    # ============================================================
    # 解析会议 + 年份
    # ============================================================
    def parse_conf(self, conf: str):
        conf_clean = conf.strip().replace("-", "").replace("_", "")
        conf_upper = conf_clean.upper()

        if conf_upper.startswith("NEURIPS"):
            year = int(conf_upper.replace("NEURIPS", ""))
            return "NeurIPS", year

        elif conf_upper.startswith("ICML"):
            year = int(conf_upper.replace("ICML", ""))
            return "ICML", year
        elif conf_upper.startswith("ICLR"):
            year = int(conf_upper.replace("ICLR", ""))
            return "ICLR", year
        else:
            raise ValueError(
                f"不支持会议 {conf}。目前支持：NeurIPSxxxx / ICMLxxxx"
            )

    # ============================================================
    # 根据会议名称自动生成 submission invitation
    # ============================================================
    def make_invitation(self, venue: str, year: int):
        """
        NeurIPS → NeurIPS.cc/{year}/Conference/-/Submission
        ICML   → ICML.cc/{year}/Conference/-/Submission
        """
        if venue == "NeurIPS":
            return f"NeurIPS.cc/{year}/Conference/-/Submission"

        if venue == "ICML":
            return f"ICML.cc/{year}/Conference/-/Submission"

        if venue == "ICLR":
            return f"ICLR.cc/{year}/Conference/-/Submission"
        raise ValueError(f"未知会议类型: {venue}")

    # ============================================================
    # 分页抓取（保持不变）
    # ============================================================
    def fetch_notes_with_retry(self, batch=1000, max_retries=10):
        all_notes = []
        offset = 0

        while True:
            for attempt in range(max_retries):
                try:
                    notes = self.client.get_notes(
                        invitation=self.inv,
                        limit=batch,
                        offset=offset,
                        details="directReplies"
                    )

                    print(f"[OK] offset={offset} 获取 {len(notes)} 条")
                    all_notes.extend(notes)

                    if len(notes) < batch:
                        return all_notes

                    offset += batch
                    break

                except (IncompleteRead, ChunkedEncodingError) as e:
                    wait = 2 ** attempt
                    print(f"[WARN] 网络断流 {e}，{wait}s 后重试 ({attempt+1}/{max_retries})")
                    time.sleep(wait)

            else:
                raise RuntimeError("多次重试仍失败，请检查网络")

    # ============================================================
    # 主逻辑（保持不变）
    # ============================================================
    def crawl(self):
        print(f"\n=== 爬取（仅 Oral/Poster/Spotlight）: {self.conf_name} ===")
        print(f"Submission Invitation = {self.inv}\n")

        print("[INFO] 开始分页抓取投稿 notes ...")
        raw_notes = self.fetch_notes_with_retry()
        print(f"[INFO] 获取到 {len(raw_notes)} 篇投稿，开始筛选轨道 ...")

        keep_keywords = ["poster", "oral", "spotlight"]
        filtered_items = []

        for note in raw_notes:
            venue = (
                note.content.get("venue", {}).get("value", "")
                if isinstance(note.content.get("venue"), dict)
                else str(note.content.get("venue", ""))
            ).lower()

            if not any(k in venue for k in keep_keywords):
                continue

            title = note.content.get("title", {}).get("value", "")
            abstract = note.content.get("abstract", {}).get("value", "")
            authors = note.content.get("authors", {}).get("value", [])
            forum = note.forum
            pdf_url = f"https://openreview.net/pdf?id={forum}"

            filtered_items.append({
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "venue": venue,
                "url": pdf_url
            })

        print(f"[INFO] 筛选出 {len(filtered_items)} 篇")

        out_file = Path(f"{self.conf_name}_oral_poster_spotlight.json")
        with open(out_file, "w", encoding="utf-8") as fw:
            json.dump(filtered_items, fw, ensure_ascii=False, indent=2)

        print(f"\n=== 完成: 已写入 {out_file} ===")
        return filtered_items


# ============================================================
# CLI（保持原样）
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--conf", type=str, required=True)
    proxy = 'http://10.101.139.60:7897'
    args = parser.parse_args()

    crawler = ConferenceCrawler(conf_name=args.conf, proxy=proxy)
    crawler.crawl()
