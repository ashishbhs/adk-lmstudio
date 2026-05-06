"""
search_tools.py — Web search tool for the Executor agent.
Uses httpx to fetch DuckDuckGo Lite results and parses them.
Returns a list of {title, url, snippet} dicts.
"""
import asyncio
import json
import re
from typing import Optional

import httpx

from local_adk.logger import setup_logger

logger = setup_logger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_DDG_URL = "https://lite.duckduckgo.com/lite/"


def _parse_results_raw(html: str, max_results: int = 8) -> list[dict]:
    """
    Parses raw HTML from DDG Lite search and extracts title/url/snippet triples.
    Uses BeautifulSoup for robust parsing against DOM structure changes.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    results = []

    # Find all anchor tags that look like search results
    for a_tag in soup.find_all('a', href=True):
        url = a_tag['href']
        
        # Skip internal DDG links, ads, or navigational links
        if not url.startswith('http') or 'duckduckgo.com' in url:
            continue
            
        title = a_tag.get_text(separator=" ", strip=True)
        if not title:
            continue
            
        # DDG Lite typical layout: the snippet is often in the next table row
        snippet = ""
        parent_tr = a_tag.find_parent('tr')
        if parent_tr:
            next_tr = parent_tr.find_next_sibling('tr')
            if next_tr:
                snippet_td = next_tr.find('td', class_='result-snippet')
                if snippet_td:
                    snippet = snippet_td.get_text(separator=" ", strip=True)
        
        # Deduplicate identical URLs
        if not any(r['url'] == url for r in results):
            results.append({"title": title, "url": url, "snippet": snippet})
            
        if len(results) >= max_results:
            break

    return results


async def google_search_async(query: str, max_results: int = 8) -> list[dict]:
    """
    Performs a web search using DDG Lite and returns a list of result dicts.
    Each dict has: title, url, snippet.
    """
    # DDG Lite uses POST requests
    data = {"q": query}
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            follow_redirects=True,
            timeout=15,
        ) as client:
            resp = await client.post(_DDG_URL, data=data)
            resp.raise_for_status()
            html = resp.text
    except httpx.HTTPError as e:
        logger.error(f"Search HTTP error: {e}")
        return [{"title": "Search Error", "url": "", "snippet": str(e)}]

    results = _parse_results_raw(html, max_results=max_results)
    logger.info(f"Web search '{query}' → {len(results)} results")
    return results


def google_search(query: str, max_results: int = 8) -> str:
    """
    ADK-compatible synchronous wrapper around google_search_async.
    Returns a JSON string of results for the agent to consume.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default 8).

    Returns:
        JSON string of search results with title, url, and snippet fields.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context — use run_in_executor trick
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, google_search_async(query, max_results))
                results = future.result(timeout=20)
        else:
            results = loop.run_until_complete(google_search_async(query, max_results))
    except Exception as e:
        logger.error(f"google_search tool error: {e}")
        results = [{"title": "Error", "url": "", "snippet": str(e)}]

    return json.dumps(results, indent=2, ensure_ascii=False)


async def fetch_page_content(url: str, max_chars: int = 4000) -> str:
    """
    Fetches the text content of a web page (stripped of HTML tags).

    Args:
        url: The URL to fetch.
        max_chars: Maximum characters to return from the page content.

    Returns:
        Extracted text content from the page, limited to max_chars characters.
    """
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            follow_redirects=True,
            timeout=15,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        return f"Could not fetch {url}: {e}"

    # Strip scripts, styles, nav
    html = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html)
    html = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html)
    html = re.sub(r'<nav[^>]*>[\s\S]*?</nav>', '', html)
    html = re.sub(r'<footer[^>]*>[\s\S]*?</footer>', '', html)
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_chars]


def fetch_page(url: str, max_chars: int = 4000) -> str:
    """
    ADK-compatible synchronous wrapper to fetch and extract text from a URL.

    Args:
        url: The URL to fetch and extract text from.
        max_chars: Maximum characters to return (default 4000).

    Returns:
        Extracted plain text content from the page.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, fetch_page_content(url, max_chars))
                return future.result(timeout=20)
        else:
            return loop.run_until_complete(fetch_page_content(url, max_chars))
    except Exception as e:
        return f"Error fetching page: {e}"
