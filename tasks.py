from celery import Celery, states
import subprocess
import os
import logging
import time
import json
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Celery
app = Celery('tasks', broker='redis://localhost:6379/0')

# Celery configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour timeout
    task_soft_time_limit=3300,  # Soft timeout at 55 minutes
    worker_max_tasks_per_child=1,  # Restart worker after each task
    worker_prefetch_multiplier=1  # Process one task at a time
)

def ensure_container_cleanup(container_name, max_retries=3):
    """Ensure a container is properly cleaned up"""
    for attempt in range(max_retries):
        try:
            # Check if container exists
            check_cmd = ['docker', 'ps', '-a', '--filter', f'name={container_name}', '--format', '{{.Names}}']
            result = subprocess.run(check_cmd, capture_output=True, text=True)
            
            if container_name in result.stdout:
                # Stop the container
                subprocess.run(['docker', 'stop', container_name], check=False)
                # Remove the container
                subprocess.run(['docker', 'rm', '-f', container_name], check=False)
                logger.info(f"Cleaned up container {container_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning up container {container_name}: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(5)
    
    return False

def run_docker_compose(batch_index, batch_size):
    """Run Docker Compose for a specific batch"""
    # Get current environment variables
    env = os.environ.copy()
    env['BATCH_INDEX'] = str(batch_index)
    env['BATCH_SIZE'] = str(batch_size)
    
    # Create a temporary compose file for this batch
    compose_content = {
        'services': {
            'scraper': {
                'build': '.',
                'volumes': ['.:/app'],
                'env_file': ['.env'],  # This ensures .env file is used
                'container_name': f'scrape101-scraper-{batch_index}',
                'environment': [
                    f'BATCH_INDEX={batch_index}',
                    f'BATCH_SIZE={batch_size}',
                    'SEQUENTIAL=false',
                    f'SUPABASE_URL={env.get("SUPABASE_URL", "")}',  # Pass Supabase URL
                    f'SUPABASE_KEY={env.get("SUPABASE_KEY", "")}',  # Pass Supabase Key
                    f'BROWSER_WS={env.get("BROWSER_WS", "")}'  # Pass Browser WS if needed
                ],
                'command': [
                    'sh', '-c',
                    'echo "Environment variables loaded:" && '
                    'echo "SUPABASE_URL: $SUPABASE_URL" && '
                    'echo "SUPABASE_KEY: $SUPABASE_KEY" && '  # Log Supabase key presence
                    'echo "BATCH_SIZE: $BATCH_SIZE" && '
                    'echo "BATCH_INDEX: $BATCH_INDEX" && '
                    'playwright install chromium && '
                    'playwright install-deps && '
                    'python scraper_groq.py'
                ],
                'networks': ['scraper-network']
            }
        },
        'networks': {
            'scraper-network': {
                'driver': 'bridge'
            }
        }
    }
    
    # Write temporary compose file
    temp_compose = f'docker-compose.{batch_index}.yml'
    with open(temp_compose, 'w') as f:
        json.dump(compose_content, f, indent=2)
    
    try:
        # Run Docker Compose with the temporary file
        cmd = ['docker', 'compose', '-f', temp_compose, 'up', '--build']
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Stream output in real-time
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                logger.info(f"Batch {batch_index}: {output.strip()}")
        
        return_code = process.wait()
        
        if return_code != 0:
            error = process.stderr.read()
            raise Exception(f"Docker Compose failed: {error}")
        
        return True
        
    finally:
        # Clean up temporary compose file
        if os.path.exists(temp_compose):
            os.remove(temp_compose)

@app.task(bind=True, max_retries=3)
def process_batch(self, batch_index, batch_size):
    """Process a single batch of URLs"""
    container_name = f"scrape101-scraper-{batch_index}"
    
    try:
        # Update task state to STARTED
        self.update_state(
            state=states.STARTED,
            meta={
                'batch_index': batch_index,
                'batch_size': batch_size,
                'status': 'Processing',
                'start_time': datetime.utcnow().isoformat()
            }
        )
        
        logger.info(f"Starting batch {batch_index} with size {batch_size}")
        
        # Ensure clean state
        ensure_container_cleanup(container_name)
        
        # Run the batch
        success = run_docker_compose(batch_index, batch_size)
        
        if not success:
            raise Exception("Docker Compose failed")
        
        # Update task state to SUCCESS
        self.update_state(
            state=states.SUCCESS,
            meta={
                'batch_index': batch_index,
                'batch_size': batch_size,
                'status': 'Completed',
                'start_time': self.info.get('start_time'),
                'end_time': datetime.utcnow().isoformat()
            }
        )
        
        logger.info(f"Completed batch {batch_index} successfully")
        return True
        
    except Exception as e:
        # Update task state to FAILURE
        self.update_state(
            state=states.FAILURE,
            meta={
                'batch_index': batch_index,
                'batch_size': batch_size,
                'status': 'Failed',
                'error': str(e),
                'start_time': self.info.get('start_time'),
                'end_time': datetime.utcnow().isoformat()
            }
        )
        
        logger.error(f"Error processing batch {batch_index}: {str(e)}")
        # Clean up on error
        ensure_container_cleanup(container_name)
        
        # Retry with exponential backoff
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            wait_time = 60 * (2 ** retry_count)
            logger.info(f"Retrying batch {batch_index} in {wait_time} seconds (attempt {retry_count + 1}/{self.max_retries})")
            self.retry(exc=e, countdown=wait_time)
        else:
            logger.error(f"Batch {batch_index} failed after {self.max_retries} retries")
            raise

if __name__ == '__main__':
    app.start() 