# newsanalyzer.py
import os
import sys
import requests
import trafilatura
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup
from newspaper import Article
from readability import Document
from goose3 import Goose
from requests.exceptions import RequestException, HTTPError, ConnectionError

# basic user agent
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"
}

def clean_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query="", fragment=""))

def extract_text_from_html(html: str, url: str) -> str:
    # trafilatura
    try:
        txt = trafilatura.extract(html, output_format="text")
        if txt and len(txt) > 100:
            return txt
    except Exception:
        pass
    # newspaper
    try:
        art = Article(url)
        art.download(input_html=html)
        art.parse()
        if art.text and len(art.text) > 100:
            return art.text
    except Exception:
        pass
    # readability
    try:
        doc_summary = Document(html).summary()
        text = BeautifulSoup(doc_summary, "lxml").get_text()
        if text and len(text) > 100:
            return text
    except Exception:
        pass
    # goose
    try:
        g = Goose()
        article = g.extract(raw_html=html)
        if article.cleaned_text and len(article.cleaned_text) > 100:
            return article.cleaned_text
    except Exception:
        pass
    # fallback - page text
    try:
        soup = BeautifulSoup(html, "html.parser")
        texts = soup.stripped_strings
        combined = " ".join(texts)
        if combined and len(combined) > 100:
            return combined
    except Exception:
        pass
    return "Could not retrieve article text."

def get_html_with_scraperapi(url: str) -> str:
    # optional: only if you set SCRAPER_KEY env var
    try:
        from scraperapi_sdk import ScraperAPIClient
        key = os.getenv("SCRAPER_KEY")
        if not key:
            return ""
        client = ScraperAPIClient(key)
        html = client.get(url, params={"render": True, "premium": True})
        return html or ""
    except Exception:
        return ""

def text(url: str) -> str:
    """
    Attempts to fetch article HTML (fast). If it fails due to 403 or other,
    returns early and background worker can try a more aggressive approach.
    """
    url = clean_url(url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        html = resp.text
        extracted = extract_text_from_html(html, url)
        if extracted and extracted != "Could not retrieve article text.":
            return extracted
    except HTTPError as e:
        # return early; background worker will try ScraperAPI or other approaches
        if e.response is not None and e.response.status_code in (403, 401):
            # return a short message that triggers background fallback
            return "BLOCKED_BY_REMOTE_SERVER"
        # other http errors - fall through to attempt scraperapi
    except (RequestException, ConnectionError) as e:
        pass

    # Try ScraperAPI fallback if available
    html = get_html_with_scraperapi(url)
    if html:
        extracted = extract_text_from_html(html, url)
        if extracted:
            return extracted

    return "Could not retrieve article text."
