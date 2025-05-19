from celery.result import AsyncResult
from tasks import process_batch
import time
import sys

def monitor_batch(task_id):
    """Monitor a single batch task"""
    result = AsyncResult(task_id)
    
    while not result.ready():
        if result.state == 'PENDING':
            print(f"Task {task_id} is pending...")
        elif result.state == 'STARTED':
            info = result.info
            print(f"Batch {info.get('batch_index')} is processing...")
            print(f"Started at: {info.get('start_time')}")
        elif result.state == 'RETRY':
            print(f"Task {task_id} is being retried...")
        time.sleep(5)
    
    if result.successful():
        info = result.info
        print(f"\nBatch {info.get('batch_index')} completed successfully!")
        print(f"Start time: {info.get('start_time')}")
        print(f"End time: {info.get('end_time')}")
    else:
        info = result.info
        print(f"\nBatch {info.get('batch_index')} failed!")
        print(f"Error: {info.get('error')}")
        print(f"Start time: {info.get('start_time')}")
        print(f"End time: {info.get('end_time')}")

def submit_and_monitor_batch(batch_index, batch_size):
    """Submit a batch and monitor its progress"""
    print(f"Submitting batch {batch_index} with size {batch_size}")
    task = process_batch.delay(batch_index, batch_size)
    print(f"Task ID: {task.id}")
    monitor_batch(task.id)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python monitor_batches.py <batch_index> <batch_size>")
        sys.exit(1)
    
    batch_index = int(sys.argv[1])
    batch_size = int(sys.argv[2])
    submit_and_monitor_batch(batch_index, batch_size) 