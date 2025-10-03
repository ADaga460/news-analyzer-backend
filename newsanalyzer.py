# newsanalyzer.py
import os
import sys
import time
import requests
import trafilatura
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup
from newspaper import Article
from readability import Document
from goose3 import Goose
from requests.exceptions import RequestException, HTTPError, ConnectionError

# optional: retry helper
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# basic user agent
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/107.0.0.0 Safari/537.36"
}


def _make_session():
    """Create a requests.Session with retries and timeouts."""
    s = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"]),
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    return s


def clean_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query="", fragment=""))


def _try_amp_variants(url: str):
    """Return a list of possible AMP-ish variants to try (best-effort)."""
    variants = []
    p = urlparse(url)
    # common patterns: /amp, /amp.html, ?outputType=amp
    if not p.path.endswith("/amp"):
        variants.append(url.rstrip("/") + "/amp")
    if not p.path.endswith(".amp.html"):
        variants.append(url.rstrip("/") + ".amp.html")
    variants.append(url + "?outputType=amp")
    return variants


def extract_text_from_html(html: str, url: str) -> str:
    """
    Attempts to retrieve the main text content from raw HTML using multiple methods.
    Order: trafilatura -> newspaper (input_html) -> readability -> goose3 -> fallback BS.
    Returns the text or "Could not retrieve article text."
    """

    # 1) trafilatura
    try:
        txt = trafilatura.extract(html, output_format="text")
        if txt and len(txt) > 120:
            return txt
    except Exception:
        pass

    # 2) newspaper (use input_html so it doesn't re-download)
    try:
        art = Article(url)
        art.download(input_html=html)
        art.parse()
        if art.text and len(art.text) > 120:
            return art.text
    except Exception:
        pass

    # 3) readability
    try:
        doc_summary = Document(html).summary()
        text = BeautifulSoup(doc_summary, "lxml").get_text(separator=" ", strip=True)
        if text and len(text) > 120:
            return text
    except Exception:
        pass

    # 4) goose3
    try:
        g = Goose()
        article = g.extract(raw_html=html)
        if getattr(article, "cleaned_text", None) and len(article.cleaned_text) > 120:
            return article.cleaned_text
    except Exception:
        pass

    # 5) fallback - page text with BeautifulSoup
    try:
        soup = BeautifulSoup(html, "html.parser")
        # try to pick article-like containers first
        selectors = [
            {"name": "article"},
            {"attrs": {"class": lambda c: c and "article" in c}},
            {"attrs": {"id": lambda i: i and "article" in i}}
        ]
        for sel in selectors:
            node = soup.find(**sel)
            if node:
                texts = node.stripped_strings
                combined = " ".join(texts)
                if combined and len(combined) > 120:
                    return combined

        # fallback: all text
        texts = soup.stripped_strings
        combined = " ".join(texts)
        if combined and len(combined) > 120:
            return combined
    except Exception:
        pass

    return "Could not retrieve article text."


def get_html_with_scraperapi(url: str) -> str:
    """
    Optional: use ScraperAPI if SCRAPER_KEY is set in env.
    Returns raw HTML string or '' if unavailable/failed.
    """
    try:
        from scraperapi_sdk import ScraperAPIClient
    except Exception:
        return ""

    key = os.getenv("SCRAPER_KEY")
    if not key:
        return ""

    try:
        client = ScraperAPIClient(key)
        html = client.get(url, params={"render": True, "premium": True})
        return html or ""
    except Exception as e:
        print(f"ScraperAPI error: {e}", file=sys.stderr)
        return ""


def _try_jina_text_extractor(url: str) -> str:
    """
    Optional public fallback: try r.jina.ai text extraction proxy.
    This is a "best-effort" fallback; it's not guaranteed and is optional.
    """
    try:
        session = _make_session()
        # jina expects the original URL after /http:// or /https:// — we send the full URL
        jina_url = f"https://r.jina.ai/http://{url.lstrip('http://').lstrip('https://')}"
        r = session.get(jina_url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=15)
        if r.ok and r.text and len(r.text) > 120:
            return r.text
    except Exception:
        pass
    return ""


def text(url: str) -> str:
    """
    Attempts to retrieve article text from a given URL.
    Primary strategy: perform a friendly GET (session + UA), extract from returned HTML.
    If the remote server blocks or returns 403, try AMP variants, jina.ai, then ScraperAPI if configured.
    """

    url = clean_url(url)
    session = _make_session()

    # first attempt: normal GET with standard headers
    try:
        resp = session.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text
        extracted = extract_text_from_html(html, url)
        if extracted and extracted != "Could not retrieve article text.":
            return extracted
    except HTTPError as he:
        # if blocked (403/401) -> try fallbacks
        status = None
        if he.response is not None:
            status = he.response.status_code
        print(f"Requests HTTPError {status} for {url}", file=sys.stderr)

        if status in (401, 403):
            # Try AMP variants (some publishers expose AMP pages)
            for amp in _try_amp_variants(url):
                try:
                    r2 = session.get(amp, headers=HEADERS, timeout=12)
                    if r2.ok and r2.text:
                        extracted = extract_text_from_html(r2.text, amp)
                        if extracted and extracted != "Could not retrieve article text.":
                            return extracted
                except Exception:
                    continue

            # Try public Jina extractor as a fallback
            jina_text = _try_jina_text_extractor(url)
            if jina_text:
                return jina_text

            # Finally try ScraperAPI (if SCRAPER_KEY set)
            html = get_html_with_scraperapi(url)
            if html:
                extracted = extract_text_from_html(html, url)
                if extracted and extracted != "Could not retrieve article text.":
                    return extracted

            # If all fails, indicate remote blocked (caller can use a background job)
            return "BLOCKED_BY_REMOTE_SERVER"

        # for other HTTP codes, fall through to try ScraperAPI
    except (RequestException, ConnectionError) as e:
        print(f"Requests exception when fetching {url}: {e}", file=sys.stderr)
        # try fallbacks below

    # Try ScraperAPI fallback if available
    html = get_html_with_scraperapi(url)
    if html:
        extracted = extract_text_from_html(html, url)
        if extracted and extracted != "Could not retrieve article text.":
            return extracted

    # Last-ditch attempt: try jina again
    jina_text = _try_jina_text_extractor(url)
    if jina_text:
        return jina_text

    return "Could not retrieve article text."
