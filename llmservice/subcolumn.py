import os
from supabase import create_client
from dotenv import load_dotenv
from llm_service import query_llm
from prompts import get_analysis_prompts
from datetime import datetime
from ollama import Client
import re
# Load environment variables
load_dotenv()

def extract_prompt_answers(response):
    
    # Find all matches of the pattern **key**\nvalue (value can be multiline)
    matches = re.findall(r'^([a-zA-Z_]+):\s*(.*)', response, re.MULTILINE)
    # Build the dictionary, stripping whitespace
    return {k: v for k, v in matches}

client = Client(
    host='https://da5eba24f40844c9ba307e11f8b8a202f.clg07azjl.paperspacegradient.com/',
)

if 'llama3.3:70b' in client.list():
    print("llama3.3:70b is available")
else:
    client.pull('llama3.3:70b')
     
# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

def fetch_and_process_data(table_name):
    try:
        # Fetch data from the specified table
        responses = supabase.table(table_name).select("*").execute()
        # Check if we got data
        if not responses:
            print(f"No data found in table {table_name}")
            return
        
        # Iterate through each ro
            
        # second layer of analysis
        for response in responses.data:
            sub_analysis_data = {}
            messages = get_analysis_prompts(**response)
            for message in messages:
                new_response = query_llm(message, client)
                sub_analysis_data.update(extract_prompt_answers(new_response))

            try:
                sub_analysis_data["url"] = response["url"]
                supabase.table("scraped_sub_analysis").insert({
                    **sub_analysis_data,
                    "analyzed_at": datetime.now().isoformat()
                }).execute()
            except Exception as e:
                        print(f"Error saving sub-analysis: {str(e)}")



    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    # Replace 'your_table_name' with your actual table name
    table_name = "scraped_analysis"
    fetch_and_process_data(table_name)
