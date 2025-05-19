import os
import logging
import time
from datetime import datetime
from dotenv import load_dotenv
import asyncio
from scraper_groq import process_urls

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def process_batch(batch_index: int, batch_size: int = 25):
    """Process a single batch of URLs directly"""
    try:
        logger.info(f"Starting batch {batch_index} with size {batch_size}")
        
        # Calculate batch range
        start = batch_index * batch_size
        end = start + batch_size
        
        # Read URLs and get batch
        with open("Buyers.csv", "r") as file:
            all_urls = file.readlines()
            batch_urls = all_urls[start:end]
        
        # Get processing mode from environment variable
        sequential = os.getenv("SEQUENTIAL", "false").lower() == "true"
        
        logger.info(f"Processing batch {batch_index + 1} with {len(batch_urls)} URLs in {'sequential' if sequential else 'concurrent'} mode")
        
        # Run the batch
        asyncio.run(process_urls(batch_urls, batch_size=5, sequential=sequential))
        
        logger.info(f"Completed batch {batch_index + 1}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing batch {batch_index}: {str(e)}")
        return False

def main():
    # Get batch parameters from environment or use defaults
    batch_index = int(os.getenv("BATCH_INDEX", 0))
    batch_size = int(os.getenv("BATCH_SIZE", 25))
    total_batches = int(os.getenv("TOTAL_BATCHES", 1))
    
    logger.info(f"Starting processing with batch_index={batch_index}, batch_size={batch_size}, total_batches={total_batches}")
    
    # Process the specified batch
    success = process_batch(batch_index, batch_size)
    
    if success:
        logger.info(f"Successfully completed batch {batch_index}")
    else:
        logger.error(f"Failed to complete batch {batch_index}")
        exit(1)

if __name__ == "__main__":
    main() 