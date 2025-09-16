# newsanalyzer.py
import sys
import time
import trafilatura
import requests
import newspaper
import torch
import random
import os

from gptreq import getRequests
from transformers import pipeline
from googlesearch import search
from newspaper import Article
from textblob import TextBlob
from newspaper import Config
from bs4 import BeautifulSoup
from goose3 import Goose
from readability import Document
from requests.exceptions import RequestException, ConnectionError, HTTPError
from scraperapi_sdk import ScraperAPIClient
from urllib.parse import urlparse, urlunparse


config = Config()

# Define a common User-Agent
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- Clean URL ---
def clean_url(url: str) -> str:
    parsed_url = urlparse(url)
    return urlunparse(parsed_url._replace(query="", fragment=""))

# --- ScraperAPI ---
def get_html_with_scraping_api(url: str) -> str:
    API_KEY = os.getenv("SCRAPER_KEY")
    client = ScraperAPIClient(API_KEY)
    try:
        html_content = client.get(url, params={'render': True, 'premium': True})
        return html_content if html_content else ""
    except Exception as e:
        print(f"ScraperAPI error: {e}", file=sys.stderr)
        return ""

# --- Extract from HTML ---
def extract_text_from_html(html_content: str, url: str) -> str:
    extracted_text = trafilatura.extract(html_content, output_format='text')
    if extracted_text and len(extracted_text) > 100:
        return extracted_text
    try:
        article = newspaper.Article(url)
        article.download(input_html=html_content)
        article.parse()
        if article.text and len(article.text) > 100:
            return article.text
    except Exception:
        pass
    try:
        doc = Document(html_content)
        extracted_text = BeautifulSoup(doc.summary(), 'lxml').get_text()
        if extracted_text and len(extracted_text) > 100:
            return extracted_text
    except Exception:
        pass
    try:
        g = Goose()
        article = g.extract(raw_html=html_content)
        if article.cleaned_text and len(article.cleaned_text) > 100:
            return article.cleaned_text
    except Exception:
        pass
    return "Could not retrieve article text."

# --- Public entrypoint: get text from URL ---
def text(url: str) -> str:
    url = clean_url(url)
    try:
        headers = {
            'User-Agent': HEADERS['User-Agent'],
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': url
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html_content = response.text
        extracted_text = extract_text_from_html(html_content, url)
        if extracted_text and extracted_text != "Could not retrieve article text.":
            return extracted_text
    except Exception as e:
        print(f"Requests error: {e}", file=sys.stderr)
    html_content = get_html_with_scraping_api(url)
    return extract_text_from_html(html_content, url)

# --- Other functions (unchanged from the user's code) ---
def split_text(text, max_words=500):
    words = text.split()
    return [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]

def summarize_article(text: str) -> str:
    summarizer = pipeline(
        "summarization",
        model="facebook/bart-large-cnn",
        device=0 if torch.cuda.is_available() else -1,
    )
    chunks = split_text(text, max_words=500)
    summaries = []
    for chunk in chunks:
        try:
            summary = summarizer(chunk, max_length=130, min_length=30, do_sample=False)[0]["summary_text"]
            summaries.append(summary)
        except Exception as e:
            print("Warning: summarization failed for a chunk:", e)

    combined = " ".join(summaries)
    if len(split_text(combined)) > 1:
        final = summarizer(combined, max_length=130, min_length=30, do_sample=False)[0]["summary_text"]
        return final
    return combined

def fetch_related(summary_text: str, url: str, hits_per_bias=5, delay=5, retries=2):
    article = newspaper.Article(url)
    try:
        article.download(headers=HEADERS)
        article.parse()
        article.nlp()
        keywords = article.keywords
    except Exception as e:
        print(f"newspaper4k download failed in fetch_related: {e}", file=sys.stderr)
        return []

    query_seed = " ".join(keywords[:10])
    results = []

    for domain, bias in DOMAIN_BIAS.items():
        query = f'{domain} {query_seed}'
        for attempt in range(retries):
            try:
                urls = list(search(query, num_results=hits_per_bias))
                time.sleep(delay + random.uniform(0, 2))
                for u in urls:
                    art = Article(u)
                    art.download(headers=HEADERS)
                    art.parse()
                    if domain in u:
                        results.append(u)
                        break
                break
            except Exception:
                continue
    return results

def polarity(text: str) -> float:
    return TextBlob(text).sentiment.polarity

def bias_score(summary: str, related):
    if not related:
        return 0.0
    return sum(polarity(t) + b for b, t in related) / len(related)

def label(score: float) -> str:
    return "Left-leaning" if score < -0.1 else "Right-leaning" if score > 0.1 else "Neutral"

def getinfo(url: str) -> list:
    print("getinfo is deprecated and not being called in the current analyze_url logic.")
    return []

def analyze_url(inputUrl: str) -> str:
    url = clean_url(inputUrl)
    print("Received URL:", url)
    try:
        article_text = text(url)

        if not article_text or article_text == "Could not retrieve article text.":
            return "Error: Could not extract any text from the article. The website may have blocked access."

        print("got article text", flush=True)
        gpt_analysis = getRequests(article_text)
        print("got gpt analysis", flush=True)

        response = f"{gpt_analysis}"
        return response
    except Exception as e:
        return f"Error analyzing article: {e}"

""" keep old CLI mode intact
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python newsanalyzer.py <article_url>")
        sys.exit(1)

    url = sys.argv[1]
    print(analyze_url(url))"""

# python3 analyze_article.py "https://www.foxnews.com/media/boston-university-college-republicans-call-security-accountability-after-charlie-kirk-assassination"
# python3 analyze_article.py "https://www.nytimes.com/2025/09/08/us/politics/trump-signature-epstein-letter.html"
# python3 analyze_article.py "https://www.infowars.com/posts/retarded-or-evil-leftist-arguments-justifying-the-murder-of-charlie-kirk"
# python3 analyze_article.py "https://www.bbc.com/news/articles/cz9je8lxge4o"
# python3 analyze_article.py "https://www.nytimes.com/2025/09/13/us/politics/charlie-kirk-legacy-trump.html?smid=nytcore-ios-share&referringSource=articleShare"
# python3 analyze_article.py "https://www.nytimes.com/2025/07/31/health/arthritis-implant-vagus-setpoint.html"

