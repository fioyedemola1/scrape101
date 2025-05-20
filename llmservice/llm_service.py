from config import SYSTEM_PROMPT
from ollama import Client

def query_llm(prompt: str, client: str = None) -> str:
    """
    Query the Ollama LLM using the generate method and return the raw response.
    
    Args:
        prompt (str): The prompt to send to the LLM
        host (str): Optional host URL for the Ollama client

    Returns:
        str: The LLM's response
    """
    try:
    
    
        response = client.chat(model='llama3.3:70b', messages=[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': prompt}])
        return response.model_dump()["message"]["content"]
    except Exception as e:
        raise e
