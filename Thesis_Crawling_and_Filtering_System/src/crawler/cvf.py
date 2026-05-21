import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import time
from tqdm import tqdm

class CVFSpider:
    def __init__(self, conference: str,
                 proxy: str = None,
                 workers: int = 10):

        """
        conference: 会议名称，如 "CVPR2025", "ICCV2023"
        proxy: 代理，如 "http://10.102.134.59:7897"，不需要代理可传 None
        workers: 并发线程数量
        """

        self.conference = conference
        self.base_url = "https://openaccess.thecvf.com"
        self.list_url = f"{self.base_url}/{conference}?day=all"
        self.workers = workers

        self.headers = {
            "User-Agent": "Mozilla/5.0"
        }

        # 代理格式 for requests
        if proxy:
            self.proxies = {
                "http": proxy,
                "https": proxy,
            }
        else:
            self.proxies = None

    # -----------------------
    # 获取所有 paper 链接
    # -----------------------
    def get_paper_links(self):
        print(f"🔍 Fetching paper list from {self.list_url} ...")

        resp = requests.get(
            self.list_url,
            headers=self.headers,
            proxies=self.proxies,
            timeout=20
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        links = set()

        for a in soup.select("a[href]"):
            href = a["href"]
            if self.conference in href and href.endswith(".html"):
                full_url = urljoin(self.base_url, href)
                links.add(full_url)

        links = sorted(list(links))
        print(f"📄 Found {len(links)} papers")
        return links

    # -----------------------
    # 解析单篇论文
    # -----------------------
    def parse_paper(self, url):
        resp = requests.get(
            url,
            headers=self.headers,
            proxies=self.proxies,
            timeout=20
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        def pick(id_):
            tag = soup.find(id=id_)
            return tag.get_text(strip=True) if tag else ""

        return {
            "title": pick("papertitle"),
            "authors": pick("authors"),
            "abstract": pick("abstract"),
            "url": url,
        }
    # 失败重试机制
    def parse_paper_with_retry(self, url, retries=5):
        """
        多线程安全的 retry wrapper，不改变 parse_paper 原逻辑。
        """
        for i in range(retries):
            try:
                return self.parse_paper(url)
            except Exception as e:
                if i < retries - 1:
                    # 指数退避（避免短时间内重复高频请求）
                    time.sleep(1.2 ** i)
                else:
                    # 最终失败，抛给外层 future
                    raise e
    # -----------------------
    # 主流程：多线程爬取全部论文
    # -----------------------
    def crawl_all(self):
        links = self.get_paper_links()
        results = []

        print(f"🚀 Using multi-threading: {self.workers} workers")

        pbar = tqdm(total=len(links), desc="📄 Crawling papers", ncols=100)

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {
                executor.submit(self.parse_paper_with_retry, url): url
                for url in links
            }

            for future in as_completed(futures):
                url = futures[future]
                try:
                    info = future.result()
                    results.append(info)
                except Exception as e:
                    pbar.set_postfix({"error": str(e)[:30]})
                finally:
                    pbar.update(1)

        pbar.close()
        print(f"\n🎉 Finished crawling {len(results)}/{len(links)} papers")

        return results

    # -----------------------
    # 保存 JSON
    # -----------------------
    def save_json(self, data, filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved to {filename}")


# ==============================================================
# 使用示例（直接运行）
# ==============================================================

if __name__ == "__main__":
    spider = CVFSpider(
        conference="ICCV2025",
        proxy="http://10.102.134.59:7897",   # 代理（可改 None）
        workers=10
    )

    data = spider.crawl_all()
    spider.save_json(data, "iccv_2025.json")
