# newsanalyzer.py
import sys
import time
import trafilatura
import requests
import newspaper
import torch
import random

from gptreq import getRequests
from transformers import pipeline
from googlesearch import search
from newspaper import Article
from textblob import TextBlob
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# The correct way to import and use a headless Chrome binary in Vercel
# You must have 'aws-lambda-selenium' in your requirements.txt
from aws_lambda_selenium.options import Options as SeleniumOptions
from aws_lambda_selenium.service import Service as SeleniumService

# Define a common User-Agent to avoid bot detection
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

LEFT = ["msnbc.com", "huffpost.com", "theguardian.com", "cnn.com"]
RIGHT = ["nypost.com", "dailywire.com", "breitbart.com"]
CENTER = ["apnews.com", "bbc.com"]
SINGLE = ["apnews.com"]

DOMAIN_BIAS = {d: -1 for d in LEFT} | {d: 0 for d in CENTER} | {d: 1 for d in RIGHT}
DOMAIN_BIAS_SINGLE = {d: 0 for d in SINGLE}


def get_html_with_selenium(url: str) -> str:
    options = SeleniumOptions()
    options.headless = True
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1280x1696')
    options.add_argument('--user-data-dir=/tmp/user-data')
    options.add_argument('--hide-scrollbars')
    options.add_argument('--single-process')
    options.add_argument('--data-path=/tmp/data-path')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--homedir=/tmp')
    options.add_argument('--disk-cache-dir=/tmp/cache-dir')

    # Pass the user agent with the options
    options.add_argument(f'user-agent={HEADERS["User-Agent"]}')

    try:
        # Use the specific Service class from aws-lambda-selenium
        service = SeleniumService()
        driver = webdriver.Chrome(service=service, options=options)
        
        # Navigate to the URL
        driver.get(url)

        # Wait for the page to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, 'body'))
        )
        
        # Return the complete page source
        return driver.page_source

    except (WebDriverException, TimeoutException) as e:
        print(f"Selenium error: {e}", file=sys.stderr)
        return ""
    finally:
        if 'driver' in locals():
            driver.quit()

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
    article.download(headers=HEADERS)
    article.parse()
    article.nlp()
    keywords = article.keywords

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

def text(url: str) -> str:
    # First, try to download with newspaper's built-in download method
    # This is a good, lightweight first attempt
    article = newspaper.Article(url)
    try:
        article.download(headers=HEADERS)
        article.parse()
        if article.text:
            return article.text
    except Exception as e:
        print(f"Newspaper3k download failed: {e}", file=sys.stderr)

    # If newspaper fails, fall back to the Selenium-based approach
    print("Newspaper3k failed, attempting to download with Selenium...", flush=True)
    downloaded_html = get_html_with_selenium(url)

    if not downloaded_html:
        print("Selenium failed to get HTML, returning empty string.")
        return ""

    # Try trafilatura first
    extracted_text = trafilatura.extract(downloaded_html)
    if extracted_text and len(extracted_text) > 100:
        return extracted_text

    # Fallback to newspaper3k if trafilatura fails
    print("Trafilatura failed, falling back to newspaper3k...")
    article = newspaper.Article(url)
    try:
        # Pass the already downloaded HTML to newspaper
        article.download(input_html=downloaded_html)
        article.parse()
        return article.text
    except Exception as e:
        print(f"Error extracting text with newspaper3k: {e}", file=sys.stderr)
        return ""


def getinfo(url: str) -> list:
    article = newspaper.Article(url)
    # Using the Selenium function to get the page content for newspaper3k
    downloaded_html = get_html_with_selenium(url)
    if not downloaded_html:
        return []

    article.download(input_html=downloaded_html)
    article.parse()
    article.nlp()
    return [article.authors, article.publish_date, article.keywords, article.tags]

def analyze_url(url: str) -> str:
    print(url)
    try:
        print("got article info", flush=True)
        article_text = text(url)

        if not article_text:
            return "Error: Could not extract any text from the article. The website may have blocked access."

        print("got article text", flush=True)
        gpt_analysis = getRequests(article_text)
        print("got gpt analysis", flush=True)

        response = f"{gpt_analysis}"
        return response
    except Exception as e:
        return f"Error analyzing article: {e}"

# keep old CLI mode intact
"""
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python newsanalyzer.py <article_url>")
        sys.exit(1)

    url = sys.argv[1]
    print(analyze_url(url))
"""