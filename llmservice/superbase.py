import os
from supabase import create_client
from dotenv import load_dotenv
from llm_service import query_llm
from prompts import get_tagging_prompts, get_return_prompts
from datetime import datetime
import time
import argparse
from transformers import AutoTokenizer
import re
from ollama import Client
from huggingface_hub import login

# Load environment variables
load_dotenv()
MAX_TOKENS = 4000
OVERLAP = 200

# Hugging Face authentication
HF_TOKEN =  "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"
if not HF_TOKEN:
    raise ValueError("Please set HUGGINGFACE_TOKEN in your .env file")
login(token=HF_TOKEN)

client = Client(
    host='https://da5eba24f40844c9ba307e11f8b8a202f.clg07azjl.paperspacegradient.com/',
)

if 'llama3.3:70b' in client.list():
    print("llama3.3:70b is available")
else:
    client.pull('llama3.3:70b')
            

def extract_clean_text(raw_text):
    # Remove HTML/XML tags
    clean = re.sub(r'<[^>]+>', '', raw_text)

    # Remove URLs
    clean = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', clean)
    
    # Remove email addresses
    clean = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', clean)
    
    # Remove special characters and symbols
    clean = re.sub(r'[^\w\s.,!?-]', ' ', clean)
    
    # Remove non-ASCII characters
    clean = re.sub(r'[^\x00-\x7F]+', ' ', clean)
    
    # Remove multiple spaces/newlines
    clean = re.sub(r'\s+', ' ', clean)
    
    # Remove leading/trailing whitespace
    clean = clean.strip()
    
    # Remove empty lines
    clean = re.sub(r'\n\s*\n', '\n', clean)
    
    # Remove common noise patterns
    clean = re.sub(r'[\[\](){}]', '', clean)  # Remove brackets and parentheses
    clean = re.sub(r'[#@]', '', clean)  # Remove hashtags and mentions
    clean = re.sub(r'[&]', 'and', clean)  # Replace & with 'and'
    
    return clean.strip()

def tokenize_text(text):
    """Tokenize text and split into chunks."""
    text = extract_clean_text(text)
    
    # Use a tokenizer that can handle longer sequences
    tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/paraphrase-MiniLM-L6-v2")
    chunks = []
    
    # Split text into sentences first
    sentences = re.split(r'(?<=[.!?])\s+', text)
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        # Tokenize the sentence
        sentence_tokens = tokenizer.encode(sentence)
        sentence_length = len(sentence_tokens)
        
        if current_length + sentence_length > MAX_TOKENS:
            # If adding this sentence would exceed the limit, save current chunk
            if current_chunk:
                chunk_text = ' '.join(current_chunk)
                chunks.append(chunk_text)
                # Keep some sentences for overlap
                overlap_sentences = current_chunk[-3:]  # Keep last 3 sentences for context
                current_chunk = overlap_sentences
                current_length = sum(len(tokenizer.encode(s)) for s in overlap_sentences)
        
        current_chunk.append(sentence)
        current_length += sentence_length
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    print(f"Split into {len(chunks)} chunks")
    return chunks



# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

def process_single_row(row, host=None):
    """Process a single row of data and return the analysis results."""
    try:
        content = row["content"]
        content_url = row["url"]
        
        # Get chunks of the content
        chunks = tokenize_text(content)
        
        # Process each chunk and combine results
        all_analysis_data = {}
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i+1}/{len(chunks)} for {row['url']}")
            prompts = get_tagging_prompts(chunk)
            
            for prompt_key, prompt_value in prompts.items():
                # Get response from LLM
                response = query_llm(prompt_value, client)
                print(f"Response received for {row['url']} chunk {i+1}")
                
                # If this is the first chunk, initialize the key
                if prompt_key not in all_analysis_data:
                    all_analysis_data[prompt_key] = response
                else:
                    # Combine responses for subsequent chunks
                    all_analysis_data[prompt_key] += " " + response

        # Add metadata
        all_analysis_data["analyzed_at"] = datetime.now().isoformat()
        all_analysis_data["url"] = content_url
        
        print(f"Saving results for {row['url']}")
        # Insert analysis data into scraped_analysis table
        supabase.table("scraped_analysis").insert({
            **all_analysis_data
        }).execute()
        
        print(f"Done for {row['url']}")
        return True
    except Exception as e:
        print(f"Error processing row with URL {row.get('url', 'unknown')}: {str(e)}")
        return False

def fetch_and_process_data(table_name, start_index=0, end_index=None, host=None):
    """
    Fetch and process data from the specified table in batches.
    
    Args:
        table_name (str): Name of the table to fetch data from
        start_index (int): Index to start processing from
        end_index (int): Index to end processing at (inclusive)
        host (str): Optional host URL for the LLM service
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
            if process_single_row(row, host):
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
    parser.add_argument('--host', type=str, help='Host URL for the LLM service')
    args = parser.parse_args()
    
    table_name = "scraped_datav2"
    fetch_and_process_data(table_name, args.start, args.end, args.host)
