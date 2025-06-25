import os
from supabase import create_client
from dotenv import load_dotenv
from llm_service import query_llm
from prompts import get_tagging_prompts 
from datetime import datetime
import time
import multiprocessing
from typing import List, Dict
import json
import csv

# Load environment variables
load_dotenv()
MAX_TOKENS = 4000
OVERLAP = 200
API_CALLS_PER_MINUTE = 1000
LLM_CALLS_PER_RECORD = 5
RECORDS_PER_MINUTE = API_CALLS_PER_MINUTE // LLM_CALLS_PER_RECORD
BATCH_WRITE_SIZE = RECORDS_PER_MINUTE  # Consumer writes in batches matching producer's minute limit

from groq import Groq

def process_record(row, groq_client):
    """Process a single record: make 5 LLM calls and return the combined result."""
    content = row["content"]
    content_url = row["url"]
    all_analysis_data = {}
    prompts = get_tagging_prompts(content)
    for prompt_key, prompt in prompts.items():
        response = query_llm(prompt, groq_client)
        response = response.split("\n\n")[1] if "\n\n" in response else response
        all_analysis_data[prompt_key] = response
    all_analysis_data["analyzed_at"] = datetime.now().isoformat()
    all_analysis_data["url"] = content_url
    all_analysis_data["model_used"] = "llama-3.1-8b-instant"
    return all_analysis_data

def producer(queue, records, api_key):
    print(f"Producer started for API key: {api_key[:8]}... with {len(records)} records")
    groq_client = Groq(api_key=api_key)
    processed = 0
    for row in records:
        try:
            result = process_record(row, groq_client)
            queue.put(result)
            processed += 1
            if processed % 10 == 0:
                print(f"Producer (key={api_key[:8]}...): Processed {processed}/{len(records)} records.")
        except Exception as e:
            print(f"Producer (key={api_key[:8]}...) - Error processing row with URL {row.get('url', 'unknown')}: {str(e)}")
    queue.put(None)

def consumer(queue, supabase_url, supabase_key, num_producers, total_records):
    """Consumer: reads from queue, writes to Supabase in batches, exits after all records are written."""
    supabase = create_client(supabase_url, supabase_key)
    batch = []
    written = 0
    done_producers = 0
    while written < total_records or done_producers < num_producers:
        item = queue.get()
        if item is None:
            done_producers += 1
            continue
        batch.append(item)
        if len(batch) >= BATCH_WRITE_SIZE:
            try:
                supabase.table("scraped_analysis").insert(batch).execute()
                written += len(batch)
                print(f"Consumer: Wrote batch of {len(batch)} records. Total written: {written}")
            except Exception as e:
                print(f"Consumer: Error writing batch: {str(e)}")
            batch = []
    # Write any remaining results
    if batch:
        try:
            supabase.table("scraped_analysis").insert(batch).execute()
            written += len(batch)
            print(f"Consumer: Wrote final batch of {len(batch)} records. Total written: {written}")
        except Exception as e:
            print(f"Consumer: Error writing final batch: {str(e)}")
    print(f"Consumer: Finished. Total records written: {written}")

def main():
    # API keys (from .env, comma-separated)
    api_keys = os.getenv("GROQ_API_KEYS", "")
    api_keys = [k for k in api_keys.split(",") if k]
    if not api_keys:
        print("Error: No API keys provided.")
        return
    # Initialize Supabase client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    supabase = create_client(supabase_url, supabase_key)
    table_name = "scraped_datav2"
    # Get all records to process
    count_response = supabase.table(table_name)\
        .select("*", count="exact")\
        .gt("crawled_at", "2025-05-26 00:00:00.311052")\
        .execute()
    total_records = count_response.count
    if total_records == 0:
        print(f"No records found in table {table_name}")
        return
    print(f"Total records to process: {total_records}")
    print("Fetching all records from Supabase...")
    all_records = []
    page_size = 1000
    for offset in range(0, total_records, page_size):
        batch = supabase.table(table_name)\
            .select("*")\
            .order("crawled_at", desc=True)\
            .gt("crawled_at", "2025-05-25 23:59:00.311052")\
            .range(offset, min(offset + page_size - 1, total_records - 1))\
            .execute().data
        all_records.extend(batch)
        print(f"Fetched {len(batch)} records (total so far: {len(all_records)})")
    print(f"Fetched {len(all_records)} records in total.")

    # Fetch all URLs from scraped_analysis
    analysis_urls = set()
    analysis_offset = 0
    while True:
        analysis_batch = supabase.table("scraped_analysis").select("url").range(analysis_offset, analysis_offset + page_size - 1).execute().data
        if not analysis_batch:
            break
        analysis_urls.update(row["url"] for row in analysis_batch if row.get("url"))
        if len(analysis_batch) < page_size:
            break
        analysis_offset += page_size
    print(f"Fetched {len(analysis_urls)} unique URLs from scraped_analysis.")

    # Filter all_records to only those whose url is NOT in analysis_urls
    filtered_records = [rec for rec in all_records if rec.get("url") not in analysis_urls]
    print(f"Filtered to {len(filtered_records)} records with URLs not in scraped_analysis.")
    all_records = filtered_records

    # Split records among producers (evenly across all API keys)
    num_producers = len(api_keys)
    records_per_producer = (len(all_records) + num_producers - 1) // num_producers  # Use filtered count
    records_batches = []
    for i in range(num_producers):
        start = i * records_per_producer
        end = min((i + 1) * records_per_producer, len(all_records))
        records_batches.append(all_records[start:end])
    for i, batch in enumerate(records_batches):
        print(f"Batch {i} assigned {len(batch)} records to API key {api_keys[i][:8]}...")
    # Set up multiprocessing
    queue = multiprocessing.Queue(maxsize=RECORDS_PER_MINUTE * num_producers * 2)
    producers = []
    for i, batch in enumerate(records_batches[::-1]):
        p = multiprocessing.Process(target=producer, args=(queue, batch, api_keys[i]))
        producers.append(p)
        p.start()
    consumer_proc = multiprocessing.Process(target=consumer, args=(queue, supabase_url, supabase_key, num_producers, total_records))
    consumer_proc.start()
    for p in producers:
        p.join()
    consumer_proc.join()
    print("All processing complete.")

if __name__ == "__main__":
    main()
