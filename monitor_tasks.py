from tasks import app
from celery.result import AsyncResult
import time
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_task_status(task_id):
    """Get the status of a specific task"""
    result = AsyncResult(task_id, app=app)
    return {
        'task_id': task_id,
        'status': result.status,
        'successful': result.successful(),
        'failed': result.failed(),
        'ready': result.ready()
    }

def monitor_tasks():
    """Monitor all tasks in the scraping queue"""
    # Get all tasks from the scraping queue
    i = app.control.inspect()
    
    # Get different types of tasks
    active = i.active() or {}
    reserved = i.reserved() or {}
    scheduled = i.scheduled() or {}
    
    # Count tasks
    total_active = sum(len(tasks) for tasks in active.values())
    total_reserved = sum(len(tasks) for tasks in reserved.values())
    total_scheduled = sum(len(tasks) for tasks in scheduled.values())
    
    logger.info(f"Active tasks: {total_active}")
    logger.info(f"Reserved tasks: {total_reserved}")
    logger.info(f"Scheduled tasks: {total_scheduled}")
    
    # Show details of active tasks
    if total_active > 0:
        logger.info("\nActive Tasks:")
        for worker, tasks in active.items():
            for task in tasks:
                logger.info(f"Worker: {worker}")
                logger.info(f"Task ID: {task['id']}")
                logger.info(f"Task Name: {task['name']}")
                logger.info(f"Started at: {task['time_start']}")
                logger.info("---")

if __name__ == '__main__':
    while True:
        try:
            monitor_tasks()
            time.sleep(10)  # Check every 10 seconds
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
            break
        except Exception as e:
            logger.error(f"Error monitoring tasks: {str(e)}")
            time.sleep(10)  # Wait before retrying 