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

# instructions to run
#uvicorn main:app --reload --host 0.0.0.0 --port 8000

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
        print("Trying trafilatura")
        txt = trafilatura.extract(html, output_format="text")
        if txt and len(txt) > 100:
            print("trafilatura succeeded")
            return txt
    except Exception:
        print("trafilatura failed")
        pass
    # newspaper
    try:
        print("Trying newspaper4k")
        art = Article(url)
        art.download()
        art.parse()
        art.nlp()
        if art.text and len(art.text) > 100:
            print("newspaper4k succeeded")
            return art.text
    except Exception:
        print("newspaper4k failed")
        pass
    # readability
    try:
        print("Trying readability-lxml")
        doc_summary = Document(html).summary()
        text = BeautifulSoup(doc_summary, "lxml").get_text()
        if text and len(text) > 100:
            print("readability-lxml succeeded")
            return text
    except Exception:
        print("readability-lxml failed")
        pass
    # goose
    try:
        print("Trying goose3")
        g = Goose()
        article = g.extract(raw_html=html)
        if article.cleaned_text and len(article.cleaned_text) > 100:
            print("goose3 succeeded")
            return article.cleaned_text
    except Exception:
        print("goose3 failed")
        pass
    # fallback - page text
    try:
        print("Trying fallback BeautifulSoup")
        soup = BeautifulSoup(html, "html.parser")
        texts = soup.stripped_strings
        combined = " ".join(texts)
        if combined and len(combined) > 100:
            print("Fallback BeautifulSoup succeeded")
            return combined
    except Exception:
        print("Fallback BeautifulSoup failed")
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
    print("Trying ScraperAPI fallback")
    html = get_html_with_scraperapi(url)
    if html:
        extracted = extract_text_from_html(html, url)
        if extracted:
            return extracted

    return "Could not retrieve article text."
