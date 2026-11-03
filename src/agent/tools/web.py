"""Free web tools: DuckDuckGo search (no key) + page fetching."""
import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool

MAX_PAGE = 8_000


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web with DuckDuckGo. Returns title, URL and snippet for each result."""
    from ddgs import DDGS

    try:
        results = DDGS().text(query, max_results=max_results)
    except Exception as e:  # rate limits happen on the free endpoint
        return f"Search failed: {e}"
    if not results:
        return "No results."
    return "\n\n".join(f"{r.get('title')}\n{r.get('href')}\n{r.get('body')}" for r in results)


@tool
def fetch_url(url: str) -> str:
    """Download a web page and return its readable text (truncated)."""
    try:
        resp = httpx.get(
            url, timeout=20, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (agentic-starter)"},
        )
        resp.raise_for_status()
    except Exception as e:
        return f"Could not fetch {url}: {e}"
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ").split())
    return text[:MAX_PAGE] + (" ... (truncated)" if len(text) > MAX_PAGE else "")
