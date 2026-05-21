#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import openreview
import json
import time
import random
from tqdm import tqdm


class ACMMMSpider:
    """
    从 OpenReview API 爬取 ACMMM Oral/Poster
    - 保留你的 API 逻辑
    - 完美加入进度条与日志格式（与 conference_crawler 一致）
    """

    def __init__(self, year="2024", proxy=None, max_retries=5):
        self.year = str(year)
        self.proxy = proxy
        self.max_retries = max_retries

        self.baseurl = "https://api2.openreview.net"
        self.client = openreview.api.OpenReviewClient(
            baseurl=self.baseurl,
        )

        # 要爬的两个 Track
        self.targets = {
            "oral":  f"MM{self.year} Oral",
            "poster": f"MM{self.year} Poster",
        }

    # ==========================================================
    # 工具：带 retry 封装的 get_notes
    # ==========================================================

    def safe_get_notes(self, content, limit=2000):
        for attempt in range(1, self.max_retries + 1):
            try:
                return self.client.get_notes(content=content, limit=limit)
            except Exception as e:
                wait = random.uniform(1, 3) * attempt
                print(
                    f"⚠️ [GET 失败] {content}  → 重试 {attempt}/{self.max_retries}, 等待 {wait:.1f}s ({e})"
                )
                time.sleep(wait)

        print(f"❌ 最终失败: {content}")
        return []

    # ==========================================================
    # Note 解析
    # ==========================================================

    @staticmethod
    def parse_note(n):
        c = n.content or {}

        def getv(x):
            if isinstance(x, dict):
                return x.get("value")
            return x

        return {
            "id": n.id,
            "url": f"https://openreview.net/forum?id={n.id}",
            "title": getv(c.get("title")),
            "abstract": getv(c.get("abstract")),
            "authors": getv(c.get("authors")) or [],
            "venue": getv(c.get("venue")),
        }

    # ==========================================================
    # 主流程
    # ==========================================================

    def crawl(self):
        all_data = {}

        print("\n======================================")
        print(f"🎯 正在爬取 ACMMM{self.year} （OpenReview）")
        print("======================================")

        total_sum = 0

        for tag, venue in self.targets.items():
            print(f"\n📥 获取：{venue}")

            notes = self.safe_get_notes(
                content={"venue": venue},
                limit=1000
            )

            print(f"   → 抓到 {len(notes)} 篇论文")
            total_sum += len(notes)

            parsed_list = []

            # ⭐解析进度条：与 conference_crawler 风格完全一样
            for n in tqdm(
                notes,
                desc=f"   🔍 正在解析 {tag} ...",
                ncols=90
            ):
                parsed_list.append(self.parse_note(n))

            all_data[tag] = parsed_list

        all_data["total"] = total_sum

        print("\n======================================")
        print(f"🎉 完成！共提取：{total_sum} 篇论文")
        print("======================================\n")

        return all_data

    # ==========================================================
    # 保存 JSON
    # ==========================================================

    @staticmethod
    def save_json(data, fname):
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"💾 保存成功: {fname}")


# ==========================================================
# 使用示例
# ==========================================================

if __name__ == "__main__":
    spider = ACMMMSpider(year="2024")
    data = spider.crawl()
    spider.save_json(data, "acmmm2024_openreview_class.json")
