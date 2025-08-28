# gptreq.py
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "factcheckdb"


def getRequests(article_text: str):
    prompt = f"""
    Analyze the language and tone used in this article about [specific topic or issue] and assess its political bias. Determine if the article leans more towards liberal, 
    conservative, or neutral stances on the issue. Provide factual evidence to support your analysis, including data, statistics, and expert opinions. Justify your scores for Fact and 
    Bias, as well as Factual Evidence, with specific examples from the text. Fact-check any claims made in the article using reputable sources such as Snopes, FactCheck.org, or 
    PolitiFact. Factual Evidence Score lowers based on its use of rhetoric, pathos, and heavily unbalanced content. If the article relies heavily on opinion, rhetoric, and unbalanced content,
    as well as lack of correct facts, lower score greatly. If the text appears to be exclusively opinionated, reduce score heavily.  Analyze political bias from known bias in news outlets 
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
    
   
    response = requests.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "stream": False})
    return response.json()["response"]
    #return(response.json()["response"])