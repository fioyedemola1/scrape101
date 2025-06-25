from config import SYSTEM_PROMPT
from ollama import Client
from typing import Union
from groq import Groq





def query_llm(prompt :Union[str, list], client: str = None) -> str:

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    if isinstance(prompt, list):
        messages.extend(prompt)
    else:
        messages.append( {"role": "user", "content": prompt })
    
    try:
        response = client.chat.completions.create(model='llama-3.1-8b-instant', messages=messages)
        return response.choices[0].message.content
    except Exception as e:
        raise e

