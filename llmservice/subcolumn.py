import os
from supabase import create_client
from dotenv import load_dotenv
from llm_service import query_llm
from prompts import get_analysis_prompts
from datetime import datetime
from ollama import Client
import re
from groq import Groq
import multiprocessing
from ratelimit import limits, sleep_and_retry
import time
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
from tqdm import tqdm
import json
from typing import Dict, List, Any
from supabase_utils import get_analysis_rows_not_in_sub_analysis

# Load configuration
def load_config() -> Dict[str, Any]:
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {
        "CALLS_PER_MINUTE": 1000,
        "MAX_RETRIES": 3,
        "RETRY_DELAY": 2,
        "CHUNK_SIZE": 10,
        "DELAY_BETWEEN_REQUESTS": 1,
        "DELAY_BETWEEN_CHUNKS": 2,
        "LOG_LEVEL": "INFO",
        "MODEL_NAME": "llama-3.1-8b-instant"
    }

# Load configuration
config = load_config()

# Configure logging
logging.basicConfig(
    level=getattr(logging, config["LOG_LEVEL"]),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('processing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def extract_prompt_answers(response):
    # Find all matches of the pattern **key**\nvalue (value can be multiline)
    matches = re.findall(r'^([a-zA-Z_]+):\s*(.*)', response, re.MULTILINE)
    # Build the dictionary, stripping whitespace
    return {k: v for k, v in matches}

# Rate limiting decorator
@sleep_and_retry
@limits(calls=config["CALLS_PER_MINUTE"], period=60)
def rate_limited_query_llm(prompt, client):
    return query_llm(prompt, client)

@retry(stop=stop_after_attempt(config["MAX_RETRIES"]), 
       wait=wait_exponential(multiplier=1, min=4, max=10))
def query_with_retry(prompt, client):
    try:
        return rate_limited_query_llm(prompt, client)
    except Exception as e:
        logger.error(f"Error querying LLM: {str(e)}")
        raise

def process_record(row, groq_client, config):
    sub_analysis_data = {}
    messages = get_analysis_prompts(**row)
    for prompt_key, prompt_value in messages.items():
        try:
            response = query_with_retry(prompt_value, groq_client)
            sub_analysis_data[prompt_key] = response
        except Exception as e:
            logging.error(f"Error processing prompt {prompt_key} for URL {row.get('url', 'unknown')}: {str(e)}")
            continue
    sub_analysis_data["url"] = row["url"]
    sub_analysis_data["processed_at"] = datetime.now().isoformat()
    sub_analysis_data["model_used"] = config["MODEL_NAME"]
    return sub_analysis_data

def producer(queue, records, api_key, config):
    print(f"Producer started for API key: {api_key[:8]}... with {len(records)} records")
    groq_client = Groq(api_key=api_key)
    processed = 0
    for row in records:
        try:
            result = process_record(row, groq_client, config)
            queue.put(result)
            processed += 1
            if processed % 10 == 0:
                print(f"Producer (key={api_key[:8]}...): Processed {processed}/{len(records)} records.")
        except Exception as e:
            print(f"Producer (key={api_key[:8]}...) - Error processing row with URL {row.get('url', 'unknown')}: {str(e)}")
    queue.put(None)

def consumer(queue, supabase_url, supabase_key, num_producers, total_records, config):
    supabase = create_client(supabase_url, supabase_key)
    batch = []
    written = 0
    done_producers = 0
    batch_size = config.get("CHUNK_SIZE", 10)
    while written < total_records or done_producers < num_producers:
        item = queue.get()
        if item is None:
            done_producers += 1
            continue
        batch.append(item)
        if len(batch) >= batch_size:
            try:
                supabase.table("scraped_sub_analysis").insert(batch).execute()
                written += len(batch)
                print(f"Consumer: Wrote batch of {len(batch)} records. Total written: {written}")
            except Exception as e:
                print(f"Consumer: Error writing batch: {str(e)}")
            batch = []
    if batch:
        try:
            supabase.table("scraped_sub_analysis").insert(batch).execute()
            written += len(batch)
            print(f"Consumer: Wrote final batch of {len(batch)} records. Total written: {written}")
        except Exception as e:
            print(f"Consumer: Error writing final batch: {str(e)}")
    print(f"Consumer: Finished. Total records written: {written}")

def main():
    load_dotenv()
    # API keys (from .env, comma-separated)
    api_keys = os.getenv("GROQ_API_KEYS", "")
    api_keys = [k for k in api_keys.split(",") if k]
    if not api_keys:
        print("Error: No API keys provided.")
        return
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    supabase = create_client(supabase_url, supabase_key)
    # Fetch only records from scraped_analysis whose url is not in scraped_sub_analysis
    all_records = get_analysis_rows_not_in_sub_analysis(supabase)
    total_records = len(all_records)
    if total_records == 0:
        print(f"No records found in scraped_analysis that are not in scraped_sub_analysis")
        return
    print(f"Total records to process: {total_records}")
    print("Fetched all records from Supabase...")
    page_size = 1000
    # The rest of the batching and multiprocessing logic remains unchanged
    num_producers = len(api_keys)
    records_per_producer = (total_records + num_producers - 1) // num_producers
    records_batches = []
    for i in range(num_producers):
        start = i * records_per_producer
        end = min((i + 1) * records_per_producer, total_records)
        records_batches.append(all_records[start:end])
    for i, batch in enumerate(records_batches):
        print(f"Batch {i} assigned {len(batch)} records to API key {api_keys[i][:8]}...")
    queue = multiprocessing.Queue(maxsize=config.get("CHUNK_SIZE", 10) * num_producers * 2)
    producers = []
    for i, batch in enumerate(records_batches):
        p = multiprocessing.Process(target=producer, args=(queue, batch, api_keys[i], config))
        producers.append(p)
        p.start()
    consumer_proc = multiprocessing.Process(target=consumer, args=(queue, supabase_url, supabase_key, num_producers, total_records, config))
    consumer_proc.start()
    for p in producers:
        p.join()
    consumer_proc.join()
    print("All processing complete.")

if __name__ == "__main__":
    main()
