# newsanalyzer.py
import sys
import time
import random
import requests
import newspaper
import torch
import trafilatura

from gptreq import getRequests
from pathlib import Path
from transformers import pipeline
from googlesearch import search
from newspaper import Article
from textblob import TextBlob

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
    # This function is not used in the `analyze_url` function, but I'll update it to use the HEADERS
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
    # First, try to download the content with our headers
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()  # This will raise an HTTPError for bad responses (4xx or 5xx)
        downloaded_html = response.text

        # Try trafilatura first, as it is often good for cleaning up content
        extracted_text = trafilatura.extract(downloaded_html)
        if len(extracted_text) > 100:
            return extracted_text
        
        # Fallback to newspaper3k if trafilatura fails to find the content
        print("Trafilatura failed, falling back to newspaper3k...")
        article = newspaper.Article(url)
        # Pass the already downloaded HTML to newspaper to avoid a second network request
        article.download(input_html=downloaded_html)
        article.parse()
        return article.text
    
    except requests.RequestException as e:
        print(f"HTTP request failed for {url}: {e}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"Error extracting text from {url}: {e}", file=sys.stderr)
        return ""

def getinfo(url: str) -> list:
    article = newspaper.Article(url)
    article.download(headers=HEADERS) # Use headers for download
    article.parse()
    article.nlp()
    return [article.authors, article.publish_date, article.keywords, article.tags]

# clean function for frontend
def analyze_url(url: str) -> str:
    print(url)
    try:
        # Note: newspaper.Article() and its methods are no longer needed here
        # since the `text()` function handles the downloading and parsing.
        
        print("got article info", flush=True)

        article_text = text(url)

        if not article_text:
            return "Error: Could not extract any text from the article."

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