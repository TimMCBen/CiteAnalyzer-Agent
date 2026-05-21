import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import json
import re
import time
import random


class ACLSpider:
    BASE = "https://aclanthology.org"

    def __init__(self, year: str, proxy=None, workers=20):
        """
        event 可以写成：
          - "ACL2024" / "ACL-2024" / "acl-2024" / "2024"
        """
        self.event_raw = 'ACL' + year
        self.event_id = self._normalize_event_id(self.event_raw)

        self.workers = workers
        self.headers = {"User-Agent": "Mozilla/5.0"}
        self.proxies = {"http": proxy, "https": proxy} if proxy else None

        # 存储 volume → category
        self.volume_category = {}  # {volume_url: "acl2024-conference" 或 "acl2024-findings"}

    # ================= 内部：标准化 event =================

    @staticmethod
    def _normalize_event_id(event: str) -> str:
        s = event.strip().lower()
        if "-" in s:
            return s

        m = re.match(r"([a-z]+)[\s_]?((19|20)\d{2}|\d{2})", s)
        if m:
            name = m.group(1)
            year = m.group(2)
            if len(year) == 2:
                year = "20" + year
            return f"{name}-{year}"

        if re.fullmatch(r"(19|20)\d{2}", s):
            return f"acl-{s}"

        return s

    # ================= 工具：带 retry 的 GET =================

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

    # ================= 获取 Volume 列表 =================

    def get_volume_links(self):
        events_url = f"{self.BASE}/events/{self.event_id}/"
        print(f"🔍 查找 {self.event_id} 的 Volume 列表…")

        resp = self.safe_get(events_url)
        if not resp:
            print("❌ 访问 events 页面失败")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        header = soup.find(lambda tag: tag.name in ("h3", "h4") and "Volumes" in tag.get_text())
        if not header:
            print("⚠️ 没找到 'Volumes' 标题，尝试全局兜底匹配…")
            candidates = soup.find_all("a", href=True)
        else:
            candidates = header.find_all_next("a", href=True)

        volume_links = set()

        for a in candidates:
            text = a.get_text(strip=True).lower()
            href = a.get("href", "")

            if not text or not href:
                continue

            # 只匹配主会（Proceedings of ACL）和 Findings
            if ("proceedings of" in text) or ("findings of" in text):

                # 必须是 /volumes/ 才接受
                if "/volumes/" not in href:
                    continue

                full = urljoin(self.BASE, href)

                anth = full.rstrip("/").split("/")[-1]

                # ====== 只保留：主会 + findings ======
                if (
                    ("acl-long" in anth) or
                    ("acl-short" in anth) or
                    ("acl-demo" in anth) or
                    ("acl-srw" in anth) or
                    ("acl-tutorial" in anth) or
                    ("findings-acl" in anth)
                ):
                    volume_links.add(full)

        # 分类用
        classified = {}
        for v in volume_links:
            anth = v.rstrip("/").split("/")[-1]
            if "findings-acl" in anth:
                classified[v] = f"{self.event_id}-findings"
            else:
                classified[v] = f"{self.event_id}-conference"  # 主会

        self.volume_category = classified

        print(f"📘（主会+Findings）共找到 {len(volume_links)} 个 Volume")
        return sorted(volume_links)

    # ================= 从 Volume 获取所有论文链接 =================

    def get_paper_links_from_volume(self, volume_url):
        resp = self.safe_get(volume_url)
        if not resp:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        paper_links = set()

        for a in soup.select("a[href]"):
            href = a["href"].strip()
            if href.endswith(".pdf"):
                continue

            m = re.match(r"^/?(20\d{2}\.[a-z0-9\.-]+\.\d+)/?$", href)
            if m:
                anth_id = m.group(1)
                full = f"{self.BASE}/{anth_id}/"
                paper_links.add(full)

        return sorted(paper_links)

    # ================= 单篇论文解析 =================

    def parse_paper(self, url, volume_url, max_retries=5):
        """
        新增：volume_url 用于判断 source
        """
        source = self.volume_category.get(volume_url, "unknown")

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

                # ===== 标题 =====
                h2 = soup.find("h2")
                if not h2:
                    raise ValueError("找不到 <h2>")

                # 只取 h2 下的第一个 <a>
                first_a = h2.find("a")

                if first_a:
                    # separator=" " 解决 "LLM"+"s" 拼接问题！
                    title = first_a.get_text(" ", strip=True)
                else:
                    title = h2.get_text(" ", strip=True)

                # ===== 作者 =====
                authors = []
                p = h2.find_next("p")
                while p:
                    a_tags = p.find_all("a")
                    if a_tags:
                        authors = [a.get_text(strip=True) for a in a_tags]
                        break
                    p = p.find_next("p")

                # ===== 摘要（新版结构 + 回退兼容）=====
                abstract = ""

                # 新版 ACL Anthology 结构：<div class="acl-abstract"><span>...</span></div>
                abs_div = soup.find("div", class_="acl-abstract")
                if abs_div:
                    spans = abs_div.find_all("span")
                    if spans:
                        abstract = " ".join(s.get_text(" ", strip=True) for s in spans)
                    else:
                        p = abs_div.find("p")
                        if p:
                            abstract = p.get_text(" ", strip=True)

                # 如果上面没找到，再回退到旧结构（2018–2020 部分论文）
                if not abstract:
                    abs_header = soup.find(
                        lambda tag: tag.name in ("h4", "h5")
                        and "Abstract" in tag.get_text()
                    )
                    if abs_header:
                        abs_p = abs_header.find_next("p")
                        if abs_p:
                            abstract = abs_p.get_text(" ", strip=True)

                # ===== anthology_id & year =====
                anth_id = url.rstrip("/").split("/")[-1]
                year = None
                m_year = re.match(r"(20\d{2})\.", anth_id)
                if m_year:
                    year = int(m_year.group(1))

                return {
                    "title": title,
                    "authors": authors,
                    "abstract": abstract,
                    "anthology_id": anth_id,
                    "year": year,
                    "url": url,
                    "source": source,
                }

            except Exception as e:
                wait = random.uniform(1, 3) * attempt
                print(
                    f"⚠️ 解析失败 [{attempt}/{max_retries}] {url} → "
                    f"{wait:.1f}s 后重试 ({e})"
                )
                time.sleep(wait)

        print(f"❌ 最终失败: {url}")
        return None


    # ================= 主流程 =================

    def crawl(self):
        volumes = self.get_volume_links()
        if not volumes:
            return []

        print("📥 并发收集全部论文链接…")

        all_results = []

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            future_to_volume = {
                pool.submit(self.get_paper_links_from_volume, v): v
                for v in volumes
            }

            volume_to_papers = {}
            for fut in tqdm(as_completed(future_to_volume), total=len(future_to_volume), desc="📘 Volumes", ncols=80):
                v = future_to_volume[fut]
                try:
                    volume_to_papers[v] = fut.result()
                except:
                    volume_to_papers[v] = []

        # 开始解析每篇论文
        print("📑 Parsing Papers…")

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            future_to_url = {}
            for v, links in volume_to_papers.items():
                for url in links:
                    future_to_url[pool.submit(self.parse_paper, url, v)] = url

            for fut in tqdm(as_completed(future_to_url), total=len(future_to_url), ncols=80):
                try:
                    data = fut.result()
                    if data:
                        all_results.append(data)
                except Exception as e:
                    print("❌ 解析失败：", future_to_url[fut], e)

        return all_results

    # ================= 保存 JSON =================

    def save_json(self, data, fname):
        with open(fname, "w", encoding="utf8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"💾 保存成功: {fname}")


# ======================
# 使用示例
# ======================
if __name__ == "__main__":
    spider = ACLSpider("acl-2025", proxy="http://10.102.134.59:7897")
    data = spider.crawl()
    spider.save_json(data, "acl_2025_all.json")
