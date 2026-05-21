import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import json
import re
import time
import random


class AAAISpider:
    BASE = "https://ojs.aaai.org"

    def __init__(self, year: str, proxy=None, workers=20):
        """
        year 可以写成：
            "AAAI2025" / "AAAI-25" / "2025" / "25"
            "AAAI2024" / "AAAI-24" / "2024" / "24"
        内部会统一转成 "AAAI-25" / "AAAI-24" 用来在页面文本里匹配。
        """
        self.year_raw = year
        self.year_token = self._normalize_year_token(year)  # 用来在文本里搜索，比如 "AAAI-24"

        self.archive_url = f"{self.BASE}/index.php/AAAI/issue/archive"
        self.workers = workers
        self.headers = {"User-Agent": "Mozilla/5.0"}
        self.proxies = {"http": proxy, "https": proxy} if proxy else None

    # ========== 内部：标准化 year ==========

    @staticmethod
    def _normalize_year_token(year: str) -> str:
        """
        把各种写法统一成 'AAAI-24' / 'AAAI-25' 这种形式，用来和
        'Vol. 38 No. 1: AAAI-24 Technical Tracks 1' 里的文本做包含匹配。
        """
        s = year.strip().upper()

        # 已经是 "AAAI-24" 这种直接用
        if "AAAI" in s and re.search(r"AAAI-\d{2}$", s):
            return s

        # 带 AAAI + 4 位年份，如 "AAAI2024" / "AAAI-2024"
        if "AAAI" in s:
            m4 = re.search(r"20(\d{2})", s)
            if m4:
                return f"AAAI-{m4.group(1)}"
            m2 = re.search(r"(\d{2})", s)
            if m2:
                return f"AAAI-{m2.group(1)}"
            # 实在解析不了就原样返回
            return s

        # 只有年份："2024" / "24"
        m4 = re.fullmatch(r"20(\d{2})", s)
        if m4:
            return f"AAAI-{m4.group(1)}"
        m2 = re.fullmatch(r"\d{2}", s)
        if m2:
            return f"AAAI-{m2.group(1)}"

        # 兜底
        return s

    # ========== 工具方法：带 retry 的 requests.get ==========

    def safe_get(self, url, max_retries=5, timeout=15):
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.get(
                    url,
                    headers=self.headers,
                    proxies=self.proxies,
                    timeout=timeout,
                )
                resp.raise_for_status()
                return resp

            except Exception as e:
                wait = random.uniform(1, 3) * attempt
                print(
                    f"⚠️ [GET 失败] {url}\n"
                    f"    第 {attempt} 次重试，等待 {wait:.1f}s... ({e})"
                )
                time.sleep(wait)

        print(f"❌ [GET 放弃] {url}")
        return None

    # ========== 获取 Issue 列表（包含分页） ==========

    def get_issue_links(self, max_archive_pages: int = 10):
        print(
            f"🔍 查找 {self.year_raw} 的 Issue 列表… "
            f"(匹配标记: {self.year_token})"
        )

        links = set()

        # archives 有分页：/issue/archive, /issue/archive/2, /issue/archive/3, ...
        for page in range(1, max_archive_pages + 1):
            if page == 1:
                url = self.archive_url
            else:
                url = f"{self.archive_url}/{page}"

            resp = self.safe_get(url)
            if not resp:
                break

            soup = BeautifulSoup(resp.text, "html.parser")

            page_links_before = len(links)

            for a in soup.select("a[href]"):
                text = a.get_text(strip=True)
                if self.year_token in text:
                    issue_url = urljoin(self.BASE, a["href"])
                    links.add(issue_url)

            # 如果这一页啥也没匹配到，而且页码>1，基本可以认为后面也没有对应年份了，可以提前停
            page_new = len(links) - page_links_before
            print(f"  📄 archive 第 {page} 页，新发现 {page_new} 个 Issue")

            # 如果这一页已经没有任何 issue view 链接，也可以停
            if not soup.select('a[href*="/issue/view/"]') and page > 1:
                break

        links = sorted(links)
        print(f"📘 共找到 {len(links)} 个 Issue")
        return links

    # ========== 从 Issue 中获取论文链接 ==========

    def get_paper_links_from_issue(self, issue_url):
        resp = self.safe_get(issue_url)
        if not resp:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        links = []

        # AAAI 2021–2025 结构
        for a in soup.select("div.obj_article_summary h3.title a[href]"):
            href = a["href"]
            if "/article/view/" in href and not href.endswith(".pdf"):
                links.append(urljoin(self.BASE, href))

        # fallback（安全兜底）
        if not links:
            for a in soup.select("h2.title a[href], h3.title a[href]"):
                href = a["href"]
                if "/article/view/" in href and not href.endswith(".pdf"):
                    links.append(urljoin(self.BASE, href))

        return links

    # ========== 单篇论文解析（带重试） ==========

    def parse_paper(self, url, max_retries=5):
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.get(
                    url,
                    headers=self.headers,
                    proxies=self.proxies,
                    timeout=15,
                )
                resp.raise_for_status()

                soup = BeautifulSoup(resp.text, "html.parser")

                # ====== 标题 ======
                title_tag = soup.find("h1", class_="page_title")
                if not title_tag:
                    raise ValueError("找不到标题标签")
                title = title_tag.get_text(strip=True)

                # ====== 作者 ======
                authors = [
                    a.get_text(strip=True)
                    for a in soup.select(".authors span.name")
                ]

                # ====== 摘要 ======
                abs_section = soup.find("section", class_="item abstract")
                abstract = abs_section.get_text(strip=True) if abs_section else ""

                # ====== 返回结构（按你要求：不写 pdf） ======
                return {
                    "title": title,
                    "authors": authors,
                    "abstract": abstract,
                    "url": url,
                }

            except Exception as e:
                wait = random.uniform(1, 3) * attempt
                print(
                    f"⚠️ 解析失败 [{attempt}/{max_retries}] {url} → {wait:.1f}s 后重试 ({e})"
                )
                time.sleep(wait)

        print(f"❌ 最终失败: {url}")
        return None

    # ========== 主流程 ==========

    def crawl(self):
        issue_links = self.get_issue_links()

        print("📥 并发收集全部论文链接...")

        all_paper_links = set()

        # ---- 并发抓取每个 Issue ----
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {
                pool.submit(self.get_paper_links_from_issue, issue): issue
                for issue in issue_links
            }

            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="📘 Issues",
                ncols=80,
            ):
                issue = futures[future]
                try:
                    links = future.result()
                    all_paper_links.update(links)
                except Exception as e:
                    print(f"❌ Issue 失败: {issue} {e}")

        all_paper_links = sorted(all_paper_links)
        print(f"📄 共找到 {len(all_paper_links)} 篇论文\n")

        # ---- 并发解析每篇论文 ----
        results = []
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {
                pool.submit(self.parse_paper, url): url
                for url in all_paper_links
            }

            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="📑 Parsing Papers",
                ncols=80,
            ):
                url = futures[future]
                try:
                    data = future.result()
                    if data:
                        results.append(data)
                except Exception as e:
                    print(f"❌ {url} {e}")

        return results

    # ========== 保存 JSON ==========

    def save_json(self, data, fname):
        with open(fname, "w", encoding="utf8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"💾 保存成功: {fname}")


# ======================
# 使用示例
# ======================
if __name__ == "__main__":
    # 你可以传 "AAAI2024" / "2024" / "AAAI-24" 都可以
    spider = AAAISpider("AAAI2023", proxy="http://10.102.134.59:7897")
    data = spider.crawl()
    spider.save_json(data, "aaai_2023.json")
