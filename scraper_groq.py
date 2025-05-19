import asyncio
import logging
import os
import sys
from crawl4ai import AsyncWebCrawler
from supabase import create_client, Client
from datetime import datetime
from typing import List, Dict
import argparse
import math

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Batch processing configuration
BATCH_INDEX = int(os.getenv("BATCH_INDEX", 0))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 10000))

class Crawler:
    def __init__(self):
        self.initial_crawl = True
        # Bright Data proxy configuration
        proxy_url = os.getenv('BROWSER_WS')
        
        # Initialize Supabase client
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase credentials not found in environment variables")
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
        self.crawler_options = {
                "timeout": 30000,
                "wait_until": "networkidle0",
                "headless": True,
                "browser_args": [
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-size=1920,1080"
                ],
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1"
                },
                "proxy": {
                    "server": proxy_url,
                },
                "max_depth": 3,
                "max_pages": 50,
                "delay": 1.0,
                "follow_links": True,
                "respect_robots_txt": True,
                "excluded_urls": [],
                "included_urls": [],
                "retry_count": 3,
                "retry_delay": 2.0
            }
        self.markdown_content = ""
        self.visited_urls = set()
        self.crawl_pages_tracker = 0
        self.base_url = ""

    def save_to_supabase(self):
        try:
            if not self.markdown_content:
                logger.warning("No content to save to Supabase")
                return None
            
            # Save raw content
            content_data = {
                "url": self.base_url,
                "content": self.markdown_content,
                "crawled_at": datetime.utcnow().isoformat(),
                "domain": self.base_url.split("//")[-1].split("/")[0]
            }
            
            content_result = self.supabase.table("scraped_datav2").insert(content_data).execute()
            logger.info(f"Successfully saved content from {self.base_url} to Supabase")
            
            return {
                "content": content_result
            }
        except Exception as e:
            logger.error(f"Error saving to Supabase: {str(e)}")
            raise

    async def crawl(self, url, crawl_pages_limit=2):
        try:
            if not self.base_url:
                self.base_url = url
                
            async with AsyncWebCrawler(**self.crawler_options) as crawler:
                if not url:
                    return None
                if url in self.visited_urls:
                    return None
                
                if self.crawl_pages_tracker >= crawl_pages_limit:
                    return None
                
                self.visited_urls.add(url)
                logger.info(f"Starting to crawl {url}")
                result = await crawler.arun(url)
                self.crawl_pages_tracker += 1
                
                if result and result.markdown:
                    if self.initial_crawl:
                        self.markdown_content = result.markdown
                        self.initial_crawl = False
                    
        except Exception as e:
            logger.error(f"An error occurred while crawling {url}: {str(e)}")
            return None

async def process_urls(urls: List[str], batch_size: int = 5, sequential: bool = False):
    """Process URLs either sequentially or concurrently based on the sequential parameter"""
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i + batch_size]
        
        if sequential:
            # Process URLs one at a time
            for url in batch:
                url = url.strip()
                if url:  # Skip empty lines
                    crawler = Crawler()
                    await crawler.crawl(url, crawl_pages_limit=2)
                    if crawler.markdown_content:  # Only save if we got content
                        crawler.save_to_supabase()
                    logger.info(f"Completed processing {url}")
        else:
            # Process URLs concurrently
            tasks = []
            for url in batch:
                url = url.strip()
                if url:  # Skip empty lines
                    crawler = Crawler()
                    async def crawl_and_save():
                        await crawler.crawl(url, crawl_pages_limit=2)
                        if crawler.markdown_content:  # Only save if we got content
                            crawler.save_to_supabase()
                    
                    tasks.append(crawl_and_save())
            
            # Wait for all tasks in the batch to complete
            await asyncio.gather(*tasks)
        
        logger.info(f"Completed batch {i//batch_size + 1} of {(len(urls) + batch_size - 1)//batch_size}")

def main():
    try:
        # Calculate batch range
        start = BATCH_INDEX * BATCH_SIZE
        end = start + BATCH_SIZE
        
        # Read URLs and get batch
        with open("Buyers.csv", "r") as file:
            all_urls = file.readlines()
            batch_urls = all_urls[start:end]
        
        # Get processing mode from environment variable
        sequential = os.getenv("SEQUENTIAL", "false").lower() == "true"
        
        logger.info(f"Processing batch {BATCH_INDEX + 1} with {len(batch_urls)} URLs in {'sequential' if sequential else 'concurrent'} mode")
        asyncio.run(process_urls(batch_urls, batch_size=5, sequential=sequential))
        logger.info(f"Completed batch {BATCH_INDEX + 1}")
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()