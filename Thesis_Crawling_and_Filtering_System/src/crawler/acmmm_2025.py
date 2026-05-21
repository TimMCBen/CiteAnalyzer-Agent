import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import time
from tqdm import tqdm


# ===============================================================
# ACMMM Spider Class
# ===============================================================
class ACMMM25Spider:
    def __init__(self, year: int, proxy: str = None, workers: int = 10):
        """
        year: 例如 2025
        proxy: 代理，如 "http://10.101.139.60:7897"
        workers: 并发线程数
        """

        self.year = year
        self.url = f"https://acmmm{year}.org/accepted-regular-papers/"
        self.workers = workers

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://dl.acm.org/",
            "DNT": "1",
            "Connection": "keep-alive",
        }

        if proxy:
            self.proxies = {"http": proxy, "https": proxy}
        else:
            self.proxies = None

    # ==============================
    # Step 1: Fetch HTML
    # ==============================
    def fetch_html(self):
        print(f"🔍 Fetching ACMMM{self.year} list page...")

        resp = requests.get(
            self.url,
            headers=self.headers,
            proxies=self.proxies,
            timeout=20
        )
        print("status =", resp.status_code)
        resp.raise_for_status()

        return resp.text

    # ==============================
    # Step 2: Parse paper list
    # ==============================
    def parse_papers(self, html):
        soup = BeautifulSoup(html, "html.parser")
        entry = soup.find("div", class_="entry-content")

        if entry is None:
            print("❌ ERROR: cannot find entry-content")
            return []

        papers = []

        for p in entry.find_all("p"):
            b = p.find("b")
            if not b:
                continue

            text = p.get_text(" ", strip=True)
            parts = text.split(" ", 1)
            if len(parts) < 2:
                continue

            pid = parts[0]
            if not pid.isdigit():
                continue

            title = b.get_text(strip=True)

            br = p.find("br")
            if not br:
                continue

            authors_text = br.next_sibling
            if not authors_text:
                continue

            authors_raw = authors_text.strip()
            authors = [a.strip() for a in authors_raw.split(",") if a.strip()]

            papers.append({
                "title": title,
                "authors": authors,
                "abstract": None
            })

        print(f"📄 Parsed {len(papers)} papers from ACMMM{self.year}")
        return papers

    # ==============================
    # Step 3: arXiv search
    # ==============================
    def search_arxiv(self, title):
        url = f"http://export.arxiv.org/api/query?search_query=ti:{quote(title)}&start=0&max_results=1"

        try:
            r = requests.get(url, proxies=self.proxies, timeout=10)
            r.raise_for_status()
            if "<entry>" not in r.text:
                return None

            soup = BeautifulSoup(r.text, "xml")
            summary = soup.find("summary")
            return summary.text.strip() if summary else None

        except:
            return None

    # ==============================
    # Step 4: ACM DL search
    # ==============================
    def search_acmdl(self, title):
        search_url = f"https://dl.acm.org/action/doSearch?AllField={quote(title)}"

        try:
            r = requests.get(search_url, headers=self.headers, proxies=self.proxies, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            hit = soup.find("h5", class_="issue-item__title")
            if not hit:
                return None

            link = hit.find("a")
            if not link:
                return None

            paper_url = "https://dl.acm.org" + link["href"]
            r2 = requests.get(paper_url, headers=self.headers, proxies=self.proxies, timeout=15)
            r2.raise_for_status()

            soup2 = BeautifulSoup(r2.text, "html.parser")
            abs_tag = soup2.find("div", class_="abstractSection")
            return abs_tag.get_text(strip=True) if abs_tag else None

        except:
            return None

    # ==============================
    # Step 5: Single abstract
    # ==============================
    def fetch_single_abstract(self, paper):
        title = paper["title"]

        abs1 = self.search_arxiv(title)
        if abs1:
            return abs1

        # abs2 = self.search_acmdl(title)
        # if abs2:
        #     return abs2

        return None

    # ==============================
    # Step 6: Multi-thread abstract search
    # ==============================
    def enrich_abstracts(self, papers):
        print(f"🚀 Fetching abstracts with {self.workers} threads...")

        fail_count = 0

        with ThreadPoolExecutor(max_workers=self.workers) as exe:
            futures = {
                exe.submit(self.fetch_single_abstract, p): idx
                for idx, p in enumerate(papers)
            }

            for future in tqdm(as_completed(futures), total=len(futures), ncols=100, desc="🔎 Abstracts"):
                idx = futures[future]

                try:
                    abs_text = future.result()
                except:
                    abs_text = None

                if abs_text:
                    papers[idx]["abstract"] = abs_text
                else:
                    papers[idx]["abstract"] = None
                    fail_count += 1

        print(f"📊 Abstract success: {len(papers) - fail_count}")
        print(f"📊 Abstract failed: {fail_count}")
        return papers

    # ==============================
    # Step 7: Crawl All
    # ==============================
    def crawl_all(self):
        html = self.fetch_html()
        papers = self.parse_papers(html)
        papers = self.enrich_abstracts(papers)
        return papers

    # ==============================
    # Step 8: 保存 JSON
    # ==============================
    def save_json(self, data, filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved to {filename}")


# ==============================================================
# 示例：直接运行
# ==============================================================
if __name__ == "__main__":
    spider = ACMMM25Spider(
        year=2025,
        proxy="http://10.101.139.60:7897",
        workers=10
    )

    data = spider.crawl_all()
    spider.save_json(data, "acmmm_2025.json")
