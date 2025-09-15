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
from newspaper import Config
from bs4 import BeautifulSoup
from goose3 import Goose
from readability import Document
from requests.exceptions import RequestException, ConnectionError, HTTPError
from scraperapi_sdk import ScraperAPIClient
from urllib.parse import urlparse, urlunparse

config = Config()

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

# --- Function to clean URL ---
def clean_url(url: str) -> str:
    """Cleans a URL by removing all query parameters and fragments."""
    parsed_url = urlparse(url)
    return urlunparse(parsed_url._replace(query="", fragment=""))

def get_html_with_scraping_api(url: str) -> str:
    """
    Fetches HTML content for a URL using the ScraperAPI service.
    """
    API_KEY = "c78fe769ae3819a8a55cb962906a2269"
    client = ScraperAPIClient(API_KEY)

    print("Trying ScraperAPI with a headless browser and premium proxies as a last resort...")
    try:
        html_content = client.get(url, params={'render': True, 'premium': True})
        
        if html_content:
            print("Successfully retrieved page using ScraperAPI.")
            return html_content
        else:
            print("ScraperAPI returned an empty response.", file=sys.stderr)
            return ""
            
    except Exception as e:
        print(f"Error calling ScraperAPI: {e}", file=sys.stderr)
        return ""

# --- New helper function for parsing HTML content ---
def extract_text_from_html(html_content: str, url: str) -> str:
    """
    Attempts to retrieve the main text content from raw HTML using multiple methods.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
    }

    print("Attempting to extract text from HTML...") # <--- DEBUGGING LINE

    # Step 1: Try `trafilatura` first as it is often very effective
    extracted_text = trafilatura.extract(html_content, output_format='text')
    if extracted_text and len(extracted_text) > 100:
        print("Using trafilatura...")
        return extracted_text

    # Step 2: Try `newspaper4k` on the raw HTML
    config = newspaper.Config()
    config.browser_user_agent = headers['User-Agent']
    article = newspaper.Article(url, config=config)
    try:
        article.download(input_html=html_content)
        article.parse()
        if article.text and len(article.text) > 100:
            print("Using newspaper4k...")
            return article.text
    except Exception as e:
        print(f"newspaper4k failed: {e}", file=sys.stderr)
    
    # Step 3: Try `readability-lxml`
    try:
        doc = Document(html_content)
        extracted_text = BeautifulSoup(doc.summary(), 'lxml').get_text()
        if extracted_text and len(extracted_text) > 100:
            print("Using readability-lxml...")
            return extracted_text
    except Exception as e:
        print(f"readability-lxml failed: {e}", file=sys.stderr)

    # Step 4: Try `goose3`
    try:
        g = Goose()
        article = g.extract(raw_html=html_content)
        if article.cleaned_text and len(article.cleaned_text) > 100:
            print("Using goose3...")
            return article.cleaned_text
    except Exception as e:
        print(f"goose3 failed: {e}", file=sys.stderr)

    # Step 5: Fallback to a basic BeautifulSoup extraction
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        content_div = soup.find('div', {'class': ['article-content', 'entry-content', 'post-content']})
        if content_div:
            extracted_text = content_div.get_text(strip=True)
            if len(extracted_text) > 100:
                print("Using fallback BeautifulSoup...")
                return extracted_text
        texts = soup.stripped_strings
        extracted_text = ' '.join(texts)
        if extracted_text and len(extracted_text) > 100:
            print("Using a basic BeautifulSoup text extraction...")
            return extracted_text
    except Exception as e:
        print(f"BeautifulSoup fallback failed: {e}", file=sys.stderr)

    return "Could not retrieve article text."


def text(url):
    """
    Attempts to retrieve the main text content from a given URL.
    ScraperAPI is used only if all other free methods fail.
    """
    html_content = ""
    
    # Step 1: Try `requests` with robust user-agent and headers
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': url
        }
        print("Attempting initial requests.get...") # <--- DEBUGGING LINE
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Requests Status Code: {response.status_code}") # <--- DEBUGGING LINE
        response.raise_for_status()
        html_content = response.text
        
        extracted_text = extract_text_from_html(html_content, url)
        if extracted_text and extracted_text != "Could not retrieve article text.":
            return extracted_text
            
    except HTTPError as e:
        print(f"Requests failed with HTTP error: {e}", file=sys.stderr)
        
        if e.response.status_code == 403:
            print("Encountered 403 Forbidden. Attempting local extraction on the returned HTML...")
            html_content = e.response.text
            extracted_text = extract_text_from_html(html_content, url)
            
            if extracted_text and extracted_text != "Could not retrieve article text.":
                return extracted_text
        
    except (RequestException, ConnectionError) as e:
        print(f"Requests failed to retrieve the page: {e}", file=sys.stderr)
    
    # Step 2: If we get here, all local methods have failed.
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

