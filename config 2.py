import os
from ollama import Client

# DeepSeek API Configuration
DEEPSEEK_API_KEY = "sk-80f5b3cd725340a487b7139df8f388d4" # Replace with your actual API key
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# System prompt for the LLM
SYSTEM_PROMPT = """You are a senior M&A analyst and ex-investment banker with deep experience in commercial due diligence and buyer targeting.
Your role is to analyze company websites and extract clear, structured business information for use in buy-side and sell-side M&A processes.
You focus on what the company actually does, how it delivers value, and in which domain — avoiding marketing language, vague benefits, or aspirational claims.
Your output is concise, analytical, and aligned with the information needs of investors and acquirers. You prioritize function over fluff, and always return structured, match-ready data that can support semantic scoring and deal logic — with no explanation.
Do include your thought process, just give the answers with no extra explanations or opinion.
Do not output introductions, analysis, features, or commentary
Return just result — no reasoning, no summary, no preamble.
"""

company = [
    "Energy Portfolio",
    "DocuSign",
    "Atomus Limited",
    "Activ Surgical",
    "Learning Technologies Group (PINX: LTTHF)",
    "Clari",
    "Allego",
    "Accurx",
    "Inprova (non-energy procurement division)",
    "Engie Impact"
]

WEBSITES = [
    "https://www.energyportfolio.co.uk",
    # "https://www.docusign.com/en-gb",
    # "https://atomus.com/",
    # "https://www.activsurgical.com",
    # "https://www.ltgplc.com",
    # "https://www.clari.com",
    # "https://www.allego.com",
    # "https://www.accurx.com",
    # "https://www.procurementforhousing.co.uk",
    # "https://www.engieimpact.com"
]

# LLM_CLIENT = Client(
#     host="http://localhost:11434",  # or your Ollama server URL
#     # headers={'x-some-header': 'some-value'}  # Optional: add headers if needed
# )