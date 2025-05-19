import os
from supabase import create_client
from dotenv import load_dotenv
from llm_service import query_llm
from prompts import get_tagging_prompts
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
        response = supabase.table(table_name).select("*").execute()
        
        # Check if we got data
        if not response.data:
            print(f"No data found in table {table_name}")
            return
        
        # Iterate through each row
        for row in response.data:
            # Iterate through each column in the row
            content = row["content"]
            content_url = row["url"]
            
            prompts = get_tagging_prompts(content[:4000])
            analysis_data = {}
            for prompt_key, prompt_value in prompts.items():
                # Get response from LLM
                response = query_llm(prompt_value)
                # Add response to analysis data
                analysis_data[prompt_key] = response

            analysis_data["analyzed_at"] = datetime.now().isoformat()
            analysis_data["url"] = content_url
                    
                    # Insert analysis data into scraped_analysis table
            try:
                supabase.table("scraped_analysis").insert({
                  
                    **analysis_data
                }).execute()
            except Exception as e:
                print(f"Error saving analysis: {str(e)}")
                
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    # Replace 'your_table_name' with your actual table name
    table_name = "scraped_datav2"
    fetch_and_process_data(table_name)
