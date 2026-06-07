"""
marketmate.mate.tools.web_search
─────────────────────────────────
Web search and page reading tools for MATE's tool-calling agent.

Multi-source search with automatic fallback:
  1. DuckDuckGo (via duckduckgo-search library)
  2. DuckDuckGo HTML (via httpx direct — bypasses library issues)
  3. Wikipedia API
  4. Brave Search API (if BRAVE_API_KEY env var set)
  5. DuckDuckGo Instant Answer API

Web page reading with content extraction:
  1. trafilatura (best quality, handles boilerplate removal)
  2. httpx + basic HTML cleanup fallback

Architecture:
  User asks "Search for X"
       ↓
  LLM calls web_search(query="X")
       ↓
  Try source 1 → fail → try source 2 → fail → try source 3
       ↓
  Return results (or helpful error)

  User asks "Read this page" or web_search returns URLs
       ↓
  LLM calls read_url(url="...")
       ↓
  Fetch page → extract main text → return readable content
       ↓
  LLM synthesizes detailed answer from full page content
"""

from __future__ import annotations

import re
import json
from typing import Any, Dict, List

import httpx

from marketmate.core.logger import get_logger

log = get_logger("mate.tools.web_search")

# Browser-like user agent to avoid bot detection
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


# ═══════════════════════════════════════════════════════════════════════════════
# Source 1: DuckDuckGo library
# ═══════════════════════════════════════════════════════════════════════════════

async def _search_ddgs_library(query: str, max_results: int = 5) -> List[Dict]:
    """Try DuckDuckGo via the duckduckgo-search library.

    Runs the synchronous DDGS call in a thread to avoid blocking
    the asyncio event loop (which would freeze loader animations
    and other concurrent requests).
    """
    try:
        from duckduckgo_search import DDGS
        import asyncio

        def _sync_search():
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))

        raw_results = await asyncio.to_thread(_sync_search)

        results = []
        for r in raw_results:
            results.append({
                "title": r.get("title", ""),
                "snippet": r.get("body", ""),
                "url": r.get("href", ""),
            })

        log.info("ddgs_library_success", query=query[:80], results=len(results))
        return results

    except ImportError:
        log.warning("ddgs_library_not_installed")
        return []
    except Exception as exc:
        log.warning("ddgs_library_failed", query=query[:80], error=str(exc))
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# Source 2: DuckDuckGo HTML via httpx (bypasses library issues on data centers)
# ═══════════════════════════════════════════════════════════════════════════════

async def _search_ddgs_html(query: str, max_results: int = 5) -> List[Dict]:
    """
    Scrape DuckDuckGo HTML search results using httpx.

    This bypasses the duckduckgo-search library's issues with
    Cloudflare protection on data center IPs.
    """
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": _BROWSER_UA},
            follow_redirects=True,
        ) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query, "kl": "wt-wt"},
            )

            if resp.status_code != 200:
                log.warning("ddgs_html_status", status=resp.status_code)
                return []

            html = resp.text
            results = []

            result_blocks = re.findall(
                r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
                r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
                html,
                re.DOTALL,
            )

            for url, title, snippet in result_blocks[:max_results]:
                title = _clean_html(title)
                snippet = _clean_html(snippet)
                actual_url = _extract_real_url(url)
                if title and actual_url:
                    results.append({
                        "title": title,
                        "snippet": snippet,
                        "url": actual_url,
                    })

            log.info("ddgs_html_success", query=query[:80], results=len(results))
            return results

    except Exception as exc:
        log.warning("ddgs_html_failed", query=query[:80], error=str(exc))
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# Source 3: DuckDuckGo Instant Answer API
# ═══════════════════════════════════════════════════════════════════════════════

async def _search_ddgs_lite(query: str, max_results: int = 5) -> List[Dict]:
    """DuckDuckGo Instant Answer API — lightweight, no scraping needed."""
    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": _BROWSER_UA},
        ) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": query,
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1,
                },
            )

            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []

            abstract = data.get("Abstract", "")
            abstract_url = data.get("AbstractURL", "")
            abstract_title = data.get("Heading", "")
            if abstract and abstract_url:
                results.append({
                    "title": abstract_title,
                    "snippet": abstract[:300],
                    "url": abstract_url,
                })

            for topic in data.get("RelatedTopics", [])[:max_results - 1]:
                if isinstance(topic, dict) and "Text" in topic and "FirstURL" in topic:
                    results.append({
                        "title": topic.get("Text", "")[:80],
                        "snippet": topic.get("Text", ""),
                        "url": topic.get("FirstURL", ""),
                    })

            log.info("ddgs_lite_success", query=query[:80], results=len(results))
            return results

    except Exception as exc:
        log.warning("ddgs_lite_failed", query=query[:80], error=str(exc))
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# Source 4: Brave Search API
# ═══════════════════════════════════════════════════════════════════════════════

async def _search_brave(query: str, max_results: int = 5) -> List[Dict]:
    """Search using Brave Search API (requires BRAVE_API_KEY env var)."""
    import os
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        return []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": api_key,
                },
                params={"q": query, "count": max_results},
            )

            if resp.status_code != 200:
                log.warning("brave_search_status", status=resp.status_code)
                return []

            data = resp.json()
            results = []
            for item in data.get("web", {}).get("results", [])[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("description", ""),
                    "url": item.get("url", ""),
                })

            log.info("brave_search_success", query=query[:80], results=len(results))
            return results

    except Exception as exc:
        log.warning("brave_search_failed", query=query[:80], error=str(exc))
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# Source 5: Wikipedia API
# ═══════════════════════════════════════════════════════════════════════════════

async def _search_wikipedia(query: str, max_results: int = 3) -> List[Dict]:
    """Search Wikipedia for factual information."""
    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": "MarketMate-Bot/1.0 (contact@marketmate.com)"},
        ) as client:
            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": max_results,
                    "format": "json",
                },
            )

            if resp.status_code != 200:
                return []

            data = resp.json()
            search_results = data.get("query", {}).get("search", [])
            if not search_results:
                return []

            results = []
            for item in search_results[:max_results]:
                title = item.get("title", "")
                snippet = _clean_html(item.get("snippet", ""))
                url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                results.append({
                    "title": title,
                    "snippet": snippet,
                    "url": url,
                    "source": "wikipedia",
                })

            # Get a summary for the top result
            if results:
                top_title = results[0]["title"]
                summary_resp = await client.get(
                    "https://en.wikipedia.org/api/rest_v1/page/summary/"
                    + top_title.replace(" ", "_"),
                )
                if summary_resp.status_code == 200:
                    summary_data = summary_resp.json()
                    extract = summary_data.get("extract", "")
                    if extract:
                        results[0]["snippet"] = extract[:400]

            log.info("wikipedia_search_success", query=query[:80], results=len(results))
            return results

    except Exception as exc:
        log.warning("wikipedia_search_failed", query=query[:80], error=str(exc))
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# Main Search Functions (with multi-source fallback)
# ═══════════════════════════════════════════════════════════════════════════════

async def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search the web using multiple sources with automatic fallback.

    Returns:
        Dict with: query, results (list of {title, snippet, url}), count, source
    """
    max_results = max(1, min(8, max_results))

    sources = [
        ("duckduckgo_library", lambda: _search_ddgs_library(query, max_results)),
        ("duckduckgo_html", lambda: _search_ddgs_html(query, max_results)),
        ("wikipedia", lambda: _search_wikipedia(query, max_results)),
        ("brave", lambda: _search_brave(query, max_results)),
        ("duckduckgo_lite", lambda: _search_ddgs_lite(query, max_results)),
    ]

    for source_name, search_fn in sources:
        try:
            results = await search_fn()
            if results:
                return {
                    "query": query,
                    "results": results[:max_results],
                    "count": len(results[:max_results]),
                    "source": source_name,
                }
        except Exception as exc:
            log.warning("web_search_source_failed", source=source_name, error=str(exc))
            continue

    log.warning("web_search_all_sources_empty", query=query[:80])
    return {
        "query": query,
        "results": [],
        "count": 0,
        "source": "all_failed",
        "hint": "No results found. Search services may be temporarily unavailable.",
    }


async def news_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search for news articles using multiple sources with fallback.

    Returns:
        Dict with: query, results (list of {title, snippet, url, source, date}), count, source
    """
    max_results = max(1, min(8, max_results))

    # Source 1: DuckDuckGo News library
    try:
        from duckduckgo_search import DDGS
        import asyncio as _asyncio

        def _sync_news_search():
            with DDGS() as ddgs:
                return list(ddgs.news(query, max_results=max_results))

        raw_results = await _asyncio.to_thread(_sync_news_search)

        results = []
        for r in raw_results:
            results.append({
                "title": r.get("title", ""),
                "snippet": r.get("body", ""),
                "url": r.get("url", r.get("href", "")),
                "source": r.get("source", ""),
                "date": r.get("date", ""),
            })

        if results:
            log.info("news_ddgs_library_success", query=query[:80], results=len(results))
            return {
                "query": query,
                "results": results,
                "count": len(results),
                "source": "duckduckgo_news",
            }
    except Exception as exc:
        log.warning("news_ddgs_library_failed", query=query[:80], error=str(exc))

    # Source 2: DuckDuckGo News via HTML
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": _BROWSER_UA},
            follow_redirects=True,
        ) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": f"{query} news", "kl": "wt-wt"},
            )

            if resp.status_code == 200:
                html = resp.text
                results = []
                result_blocks = re.findall(
                    r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
                    r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
                    html,
                    re.DOTALL,
                )
                for url, title, snippet in result_blocks[:max_results]:
                    title = _clean_html(title)
                    snippet = _clean_html(snippet)
                    actual_url = _extract_real_url(url)
                    if title and actual_url:
                        results.append({
                            "title": title,
                            "snippet": snippet,
                            "url": actual_url,
                            "source": "duckduckgo",
                            "date": "",
                        })

                if results:
                    log.info("news_ddgs_html_success", query=query[:80], results=len(results))
                    return {
                        "query": query,
                        "results": results,
                        "count": len(results),
                        "source": "duckduckgo_news_html",
                    }
    except Exception as exc:
        log.warning("news_ddgs_html_failed", query=query[:80], error=str(exc))

    # Source 3: Wikipedia fallback
    wiki_results = await _search_wikipedia(query, max_results)
    if wiki_results:
        return {
            "query": query,
            "results": wiki_results,
            "count": len(wiki_results),
            "source": "wikipedia_fallback",
            "hint": "News search unavailable. Showing Wikipedia results instead.",
        }

    return {
        "query": query,
        "results": [],
        "count": 0,
        "source": "all_failed",
        "hint": "No news results found. Search services may be temporarily unavailable.",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Web Page Reading — extract full content from a URL
# ═══════════════════════════════════════════════════════════════════════════════

_MAX_PAGE_CONTENT = 8000


async def read_url(url: str, max_length: int = _MAX_PAGE_CONTENT) -> Dict[str, Any]:
    """
    Read a web page and extract its main text content.

    Uses multiple extraction methods with automatic fallback:
      1. trafilatura — best quality, handles boilerplate removal natively
      2. httpx + basic HTML cleanup — always-available fallback

    Returns:
        Dict with url, title, content, content_length, truncated, method
        Or on failure: url, error
    """
    if not url or not url.strip().startswith("http"):
        return {
            "url": url,
            "error": "Invalid URL. Must start with http:// or https://",
        }

    url = url.strip()

    # Try trafilatura first
    try:
        content, title, method = await _read_with_trafilatura(url)
        if content:
            truncated = len(content) > max_length
            return {
                "url": url,
                "title": title or "",
                "content": content[:max_length],
                "content_length": len(content),
                "truncated": truncated,
                "method": method,
            }
    except Exception as exc:
        log.warning("read_url_trafilatura_failed", url=url[:100], error=str(exc))

    # Fallback: httpx + basic HTML cleanup
    try:
        content, title, method = await _read_with_httpx(url)
        if content:
            truncated = len(content) > max_length
            return {
                "url": url,
                "title": title or "",
                "content": content[:max_length],
                "content_length": len(content),
                "truncated": truncated,
                "method": method,
            }
    except Exception as exc:
        log.warning("read_url_httpx_failed", url=url[:100], error=str(exc))

    log.warning("read_url_all_methods_failed", url=url[:100])
    return {
        "url": url,
        "error": (
            "Could not read this page. The site may be blocking automated access, "
            "require JavaScript rendering, or be behind a paywall."
        ),
    }


async def _read_with_trafilatura(url: str) -> tuple:
    """Extract page content using trafilatura (gold standard)."""
    import trafilatura

    async with httpx.AsyncClient(
        timeout=20.0,
        headers={"User-Agent": _BROWSER_UA},
        follow_redirects=True,
    ) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            raise ValueError(f"HTTP {resp.status_code}")
        html = resp.text

    content = trafilatura.extract(
        html,
        favor_precision=True,
        include_comments=False,
        include_tables=True,
    )

    if not content:
        raise ValueError("trafilatura extracted no content")

    metadata = trafilatura.extract(html, output_format="json", favor_precision=True)
    title = ""
    if metadata:
        try:
            meta_dict = json.loads(metadata)
            title = meta_dict.get("title", "")
        except (json.JSONDecodeError, TypeError):
            pass

    log.info("read_url_trafilatura_success", url=url[:80], content_len=len(content))
    return content, title, "trafilatura"


async def _read_with_httpx(url: str) -> tuple:
    """Extract page content using httpx + basic HTML cleanup (always-available fallback)."""
    async with httpx.AsyncClient(
        timeout=20.0,
        headers={"User-Agent": _BROWSER_UA},
        follow_redirects=True,
    ) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            raise ValueError(f"HTTP {resp.status_code}")
        html = resp.text

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = _clean_html(title_match.group(1)) if title_match else ""

    cleaned = re.sub(
        r"<(script|style|nav|footer|header|aside|noscript)[^>]*>.*?</\1>",
        "", html, flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = _clean_html(cleaned)

    if not cleaned or len(cleaned.strip()) < 50:
        raise ValueError("No meaningful content extracted from page")

    log.info("read_url_httpx_success", url=url[:80], content_len=len(cleaned))
    return cleaned, title, "httpx_basic"


# ═══════════════════════════════════════════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════════════════════════════════════════

def _clean_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'")
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_real_url(ddg_url: str) -> str:
    """Extract the real URL from a DuckDuckGo redirect URL."""
    match = re.search(r"uddg=([^&]+)", ddg_url)
    if match:
        from urllib.parse import unquote
        return unquote(match.group(1))
    if ddg_url.startswith("http"):
        return ddg_url
    return ""
