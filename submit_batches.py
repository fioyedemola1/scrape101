import os
from tasks import app
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def submit_batches():
    # Configuration
    TOTAL_RECORDS = 1091
    BATCH_SIZE = 25
    TOTAL_BATCHES = (TOTAL_RECORDS + BATCH_SIZE - 1) // BATCH_SIZE  # Ceiling division
    
    logger.info(f"Submitting {TOTAL_BATCHES} batches for processing")
    
    # Submit each batch as a Celery task
    for batch_index in range(TOTAL_BATCHES):
        # Calculate start and end indices for logging
        start = batch_index * BATCH_SIZE
        end = min(start + BATCH_SIZE, TOTAL_RECORDS)
        
        logger.info(f"Submitting batch {batch_index} (URLs {start}-{end-1})")
        
        # Submit the task to Celery
        app.send_task(
            'tasks.process_batch',
            args=[batch_index, BATCH_SIZE],
            queue='scraping'  # Use a dedicated queue for scraping tasks
        )
    
    logger.info("All batches submitted successfully")

if __name__ == '__main__':
    submit_batches() 