import os
from supabase import create_client
from tiktoken import encoding_for_model
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

def get_token_count(text, model="gpt-3.5-turbo"):
    """
    Calculate the number of tokens in a text using the specified model's tokenizer.
    """
    if not text or not isinstance(text, str):
        return 0
    
    enc = encoding_for_model(model)
    return len(enc.encode(text))

def calculate_column_tokens(table_name, column_name, model="gpt-3.5-turbo"):
    """
    Calculate tokens for all rows in a specified column of a Supabase table.
    
    Args:
        table_name (str): Name of the Supabase table
        column_name (str): Name of the column to calculate tokens for
        model (str): Model to use for tokenization (default: gpt-3.5-turbo)
    
    Returns:
        dict: Dictionary containing total tokens and token counts per row
    """
    try:
        # Fetch data from Supabase
        response = supabase.table(table_name).select(column_name).execute()
        
        if not response.data:
            return {"error": "No data found in the specified table/column"}
        
        # Calculate tokens for each row
        token_counts = []
        total_tokens = 0
        
        for row in response.data:
            text = row.get(column_name)
            tokens = get_token_count(text, model)
            token_counts.append({
                "row_id": row.get("id", "unknown"),
                "tokens": tokens,
                "text": text[:100] + "..." if text and len(text) > 100 else text
            })
            total_tokens += tokens
        
        return {
            "total_tokens": total_tokens,
            "row_count": len(token_counts),
            "token_counts": token_counts
        }
    
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # Example usage
    table_name = "scraped_datav2"  # Replace with your table name
    column_name = "content"  # Replace with your column name
    
    result = calculate_column_tokens(table_name, column_name)
    
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Total tokens: {result['total_tokens']}")
        print(f"Number of rows: {result['row_count']}")
        print("\nToken counts per row:")
        for count in result['token_counts']:
            print(f"Row ID: {count['row_id']}, Tokens: {count['tokens']}")
