import os
from supabase import create_client
from dotenv import load_dotenv
from llm_service import query_llm
from prompts import get_tagging_prompts, get_return_prompts
from datetime import datetime
import time
import argparse

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

def process_single_row(row):
    """Process a single row of data and return the analysis results."""
    try:
        content = row["content"]
        content_url = row["url"]
        
        prompts = get_tagging_prompts(content[:4000])
        analysis_data = {}
        print(f"Processing row {row['url']}")
        for prompt_key, prompt_value in prompts.items():
            # Get response from LLM
            response = query_llm(prompt_value)
            # Add response to analysis data
            analysis_data[prompt_key] = response

        analysis_data["analyzed_at"] = datetime.now().isoformat()
        analysis_data["url"] = content_url
        
        print(f"saving results for {row['url']}")
        # Insert analysis data into scraped_analysis table
        supabase.table("scraped_analysis").insert({
            **analysis_data
        }).execute()
        
        print(f"Done for {row['url']}")
        return True
    except Exception as e:
        print(f"Error processing row with URL {row.get('url', 'unknown')}: {str(e)}")
        return False

def fetch_and_process_data(table_name, start_index=0, end_index=None):
    """
    Fetch and process data from the specified table in batches.
    
    Args:
        table_name (str): Name of the table to fetch data from
        start_index (int): Index to start processing from
        end_index (int): Index to end processing at (inclusive)
    """
    try:
        # Fetch total count of rows
        count_response = supabase.table(table_name).select("*", count="exact").execute()
        total_rows = count_response.count
        
        if total_rows == 0:
            print(f"No data found in table {table_name}")
            return
        
        # Set end_index to total_rows if not specified
        if end_index is None:
            end_index = total_rows - 1
        
        print(f"Total rows in table: {total_rows}")
        print(f"Processing range: {start_index} to {end_index}")
        
        # Fetch batch of data
        response = supabase.table(table_name).select("*").range(start_index, end_index).execute()
        
        if not response.data:
            print(f"No data found in range {start_index} to {end_index}")
            return
        
        # Process each row in the batch
        successful = 0
        failed = 0
        for row in response.data:
            if process_single_row(row):
                successful += 1
            else:
                failed += 1
            # Add a small delay to avoid overwhelming the API
            time.sleep(1)
        
        print(f"Batch completed: {successful} successful, {failed} failed")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process data from Supabase in batches')
    parser.add_argument('--start', type=int, default=0, help='Start index for processing')
    parser.add_argument('--end', type=int, help='End index for processing (inclusive)')
    args = parser.parse_args()
    
    table_name = "scraped_datav2"
    fetch_and_process_data(table_name, args.start, args.end)
