import sys
import time
import random
import requests
import newspaper
import torch

from api.gptreq import getRequests
from pathlib import Path
from transformers import pipeline
from googlesearch import search
from newspaper import Article
from textblob import TextBlob

LEFT  = ["msnbc.com", "huffpost.com", "theguardian.com", "cnn.com"]
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
    article = newspaper.Article(url)
    article.download()
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
                    art.download()
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
    article = newspaper.Article(url)
    article.download()
    article.parse()
    return article.text

def getinfo(url: str):
    article = newspaper.Article(url)
    article.download()
    article.parse()
    article.nlp()
    return [article.authors, article.publish_date, article.keywords, article.tags]

# clean function for frontend
def analyze_url(url: str) -> str:
    try:
        print(url)
        info = getinfo(url)
        print("got article info")
        article_text = text(url)
        summary = summarize_article(article_text)
        print("summarized article")
        gpt_analysis = getRequests(article_text)
        print("got gpt analysis")
        related = fetch_related(summary, url)
        print("fetched related articles")

        response = f"Authors: {info[0]}\nDate: {info[1]}\nKeywords: {info[2]}\nTags: {info[3]}\n\nSummary:\n{summary}\n\nGPT Analysis:\n{gpt_analysis}\n\nRelated Articles:\n{chr(10).join(related) if related else "None"}"
        return response
    except Exception as e:
        return f"Error analyzing article: {e}"

# keep old CLI mode intact
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python newsanalyzer.py <article_url>")
        sys.exit(1)

    url = sys.argv[1]
    print(analyze_url(url))
