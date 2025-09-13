# gptreq.py
import os
import requests



def getRequests(article_text: str):
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_KEY")  # from render
    MODEL = "mistralai/mistral-small-3.2-24b-instruct:free"
    
    prompt = f"""
    Analyze the language and tone used in this article about [specific topic or issue] and assess its political bias. Determine if the article leans more towards liberal, 
    conservative, or neutral stances on the issue. Provide factual evidence to support your analysis, including data, statistics, and expert opinions. Justify your scores for Fact and 
    Bias, as well as Factual Evidence, with specific examples from the text. Fact-check any claims made in the article using reputable sources such as Snopes, FactCheck.org, or 
    PolitiFact. Factual Evidence Score lowers based on its use of rhetoric, pathos, and heavily unbalanced content. If the article relies heavily on opinion, rhetoric, and unbalanced content,
    as well as lack of correct facts, lower factual score greatly. If the text appears to be exclusively opinionated, increase bias score heavily.  Analyze political bias from known bias in news outlets 
    (for example, AP News is center, Fox is known to be right, and NYTimes is known to be slightly left leaning), and due to article content.

    Below is the format you must adhere to, where everything in brackets is filled in with what is relevent from the article:

    Factual Evidence Score: 
        * [Score out of 10]

    Bias Score (The lower, the better):
        * [Score out of 10]

    Assessing Political Bias:
        Based on the content and tone of the article, I would conclude it leans [position]. Here is why: [explanation]

    Language and Tone:
        The article uses [description] of [political position] language. The use of [explain here]

        1. Language: 
        2. Policy content: 
        3. Contrast with [opposition] position: 

    Fact-checking claims:

        1. PolitiFact: [State fact that is mentioned in article, and explain why it may or may not be correct]
        2. Snopes: [State fact that is mentioned in article, and explain why it may or may not be correct]
        3. FactCheck.org: [State fact that is mentioned in article, and explain why it may or may not be correct]

    Conclusion:
        [Concluding sentence here]

    Text:
    {article_text}
    """

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://news-analyzer-frontend-plat.vercel.app/",  # optional but recommended
        "X-Title": "News Analyzer",                # optional
    }

    data = {
        "model": MODEL,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that analyzes political bias and factual accuracy in news articles. You deal with only facts, and detect possible areas for bias with un"},
            {"role": "user", "content": prompt},
        ],
    }

    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)

    if response.status_code != 200:
        raise Exception(f"OpenRouter API error: {response.status_code}, {response.text}")

    return response.json()["choices"][0]["message"]["content"]
