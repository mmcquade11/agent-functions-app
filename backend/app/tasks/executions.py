from typing import List, Dict, Any
import logging
from datetime import datetime, timedelta
import asyncio

from app.tasks.worker import celery_app, AsyncTask
#from app.services.executor import (
    #start_workflow_execution,
    #get_workflow_execution,
    #update_workflow_execution_status
#)
from app.services.scheduler import process_scheduled_workflows
from app.websockets.manager import websocket_manager


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.executions.run_workflow_execution_task")
def run_workflow_execution_task(self, execution_id: str):
    """
    Celery task to run a workflow execution.
    This is a synchronous wrapper around the async execution function.
    """
    logger.info(f"Starting execution task for execution ID: {execution_id}")
    
    task = AsyncTask()
    db = task.get_db()
    
    try:
        # Run the execution
        result = task.run_async(start_workflow_execution, db, execution_id)
        return {"status": "success", "execution_id": execution_id, "result": result}
    except Exception as e:
        logger.error(f"Error running execution {execution_id}: {str(e)}")
        
        # Update execution status to failed
        try:
            task.run_async(
                update_workflow_execution_status,
                db,
                execution_id,
                "failed",
                error_message=str(e)
            )
            
            # Broadcast error to WebSocket clients
            task.run_async(
                websocket_manager.broadcast_log,
                execution_id,
                {
                    "level": "ERROR",
                    "message": f"Execution failed: {str(e)}",
                    "metadata": {"error": str(e)}
                }
            )
        except Exception as update_error:
            logger.error(f"Error updating failed execution status: {str(update_error)}")
        
        # Re-raise the exception to mark the task as failed
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="app.tasks.executions.process_scheduled_workflows_task")
def process_scheduled_workflows_task(self):
    """
    Celery task to process scheduled workflows that are due to run.
    This is scheduled to run every minute by the Celery beat scheduler.
    """
    logger.info("Running scheduled workflow processor")
    
    task = AsyncTask()
    db = task.get_db()
    
    try:
        # Process due schedules
        execution_ids = task.run_async(process_scheduled_workflows, db)
        return {
            "status": "success", 
            "executions_started": len(execution_ids),
            "execution_ids": execution_ids
        }
    except Exception as e:
        logger.error(f"Error processing scheduled workflows: {str(e)}")
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="app.tasks.executions.cleanup_old_executions_task")
def cleanup_old_executions_task(self, days_to_keep: int = 30):
    """
    Celery task to clean up old execution records.
    This is scheduled to run periodically by the Celery beat scheduler.
    
    Args:
        days_to_keep: Number of days of execution records to keep (default: 30)
    """
    logger.info(f"Cleaning up execution records older than {days_to_keep} days")
    
    # Calculate cutoff date
    cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
    
    # TODO: Implement deletion logic for old executions
    # This would typically archive or delete execution records and logs
    # older than the cutoff date
    
    return {"status": "success", "cutoff_date": cutoff_date.isoformat()}


async def run_workflow_execution_task(execution_id: str):
    """
    Async function to start a workflow execution task.
    This is a wrapper around the Celery task for use in async code.
    """
    # Queue the Celery task
    task = run_workflow_execution_task.delay(execution_id)
    
    return {"task_id": task.id, "execution_id": execution_id}
