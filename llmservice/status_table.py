import os
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

# List of tables to check for URLs
TABLES = [
    "new_scrap",
    "scraped_datav2",
    "scraped_analysis",
    "scraped_sub_analysis",
    "BuyersUrl",
    "BuyersUrl_Batch2",
    "BuyersUrl_Batch3"
]

# Helper function to fetch all unique URLs from a table
def fetch_unique_urls(table_name):
    urls = set()
    page_size = 1000
    offset = 0
    while True:
        batch = supabase.table(table_name).select("url").range(offset, offset + page_size - 1).execute().data
        if not batch:
            break
        urls.update(row["url"] for row in batch if row.get("url"))
        offset += page_size
    return urls

# Prefer new_scrap, but if empty, use scraped_datav2
print("Checking new_scrap for URLs...")
new_scrap_urls = fetch_unique_urls("new_scrap")
if not new_scrap_urls:
    print("new_scrap is empty, using scraped_datav2 instead.")
    new_scrap_urls = fetch_unique_urls("scraped_datav2")

# Fetch URLs from all other tables
scraped_analysis_urls = fetch_unique_urls("scraped_analysis")
scraped_sub_analysis_urls = fetch_unique_urls("scraped_sub_analysis")
buyers_url_urls = fetch_unique_urls("BuyersUrl")
buyers_url_batch2_urls = fetch_unique_urls("BuyersUrl_Batch2")
buyers_url_batch3_urls = fetch_unique_urls("BuyersUrl_Batch3")

# Union of all URLs
all_urls = (
    new_scrap_urls |
    scraped_analysis_urls |
    scraped_sub_analysis_urls |
    buyers_url_urls |
    buyers_url_batch2_urls |
    buyers_url_batch3_urls
)

print(f"Total unique URLs found: {len(all_urls)}")

# Build status rows
status_rows = []
for url in all_urls:
    status_rows.append({
        "url": url,
        "in_new_scrap": url in new_scrap_urls,
        "in_scraped_datav2": url in new_scrap_urls,  # If new_scrap is empty, this is scraped_datav2
        "in_scraped_analysis": url in scraped_analysis_urls,
        "in_scraped_sub_analysis": url in scraped_sub_analysis_urls,
        "in_buyersurl": url in buyers_url_urls,
        "in_buyersurl_batch2": url in buyers_url_batch2_urls,
        "in_buyersurl_batch3": url in buyers_url_batch3_urls,
    })

# Upsert status rows into scrape_status table
batch_size = 1000
for i in range(0, len(status_rows), batch_size):
    batch = status_rows[i:i+batch_size]
    supabase.table("scrape_status").upsert(batch, on_conflict="url").execute()
    print(f"Upserted {i + len(batch)} of {len(status_rows)} rows...")

print(f"Wrote {len(status_rows)} status rows to scrape_status table.")
