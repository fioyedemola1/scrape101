from config import SYSTEM_PROMPT
from ollama import Client

def query_llm( prompt: str) -> str:
    """
    Query the Ollama LLM using the generate method and return the raw response.
    
    Args:
        prompt (str): The prompt to send to the LLM

    Returns:
        str: The LLM's response
    """
    try:
        
        client = Client(
        # host='http://159.203.3.54',
        host='https://baa5-34-41-134-125.ngrok-free.app',
        headers={'x-some-header': 'some-value'}
        )
    
        response = client.chat(model='llama3.3:70b', messages=[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': prompt}])
        return response.model_dump()["message"]["content"]
    except Exception as e:
        raise e
