import os
from supabase import create_client
from dotenv import load_dotenv
from llm_service import query_llm
from prompts import get_tagging_prompts, get_return_prompts
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

def fetch_and_process_data(table_name):
    try:
        # Fetch data from the specified table
        responses = supabase.table(table_name).select("*").execute()
        sub_analysis_data = {}
        # Check if we got data
        if not responses:
            print(f"No data found in table {table_name}")
            return
        
        # Iterate through each ro
            
        # second layer of analysis
        for response in responses.data:
            prompts = get_return_prompts(response)
            for prompt_key, prompt_value in prompts.items():
                for key, value in prompt_value.items():
                    new_response = query_llm(value)
                    sub_analysis_data[key] = new_response
                    try:
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
