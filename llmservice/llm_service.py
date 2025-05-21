from config import SYSTEM_PROMPT
from ollama import Client
from typing import Union

def query_llm(prompt :Union[str, list], client: str = None) -> str:

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    if isinstance(prompt, list):
        messages.extend(prompt)
    else:
        messages.append( {"role": "user", "content": prompt })
    
    try:
        response = client.chat(model='llama3.3:70b', messages=messages)
        return response.model_dump()["message"]["content"]
    except Exception as e:
        raise e
