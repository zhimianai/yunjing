import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup


class WebSearcher:

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.session = requests.Session()
        retry_strategy = Retry(total=2, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def search(self, query: str, max_results: int = 5) -> str:
        try:
            url = "https://duckduckgo.com/html/"
            params = {"q": query}

            response = self.session.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            results = []

            for result in soup.find_all('div', class_='result')[:max_results]:
                title_elem = result.find('a', class_='result__a')
                snippet_elem = result.find('a', class_='result__snippet')

                if title_elem:
                    title = title_elem.get_text(strip=True)
                    link = title_elem.get('href', '')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

                    results.append(f"标题: {title}\n链接: {link}\n摘要: {snippet}\n")

            if not results:
                return ""

            return "\n".join(results)

        except Exception as e:
            return ""

    def search_with_bing(self, query: str, api_key: str = None, max_results: int = 5) -> str:
        if not api_key:
            return self.search(query, max_results)

        try:
            url = "https://api.bing.microsoft.com/v7.0/search"
            headers = {
                "Ocp-Apim-Subscription-Key": api_key
            }
            params = {
                "q": query,
                "count": max_results
            }

            response = self.session.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            results = []

            for item in data.get("webPages", {}).get("value", []):
                title = item.get("name", "")
                url_link = item.get("url", "")
                snippet = item.get("snippet", "")

                results.append(f"标题: {title}\n链接: {url_link}\n摘要: {snippet}\n")

            if not results:
                return ""

            return "\n".join(results)

        except Exception as e:
            return ""