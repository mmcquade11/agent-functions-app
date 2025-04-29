from celery import Celery
from celery.schedules import crontab
import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal


logger = logging.getLogger(__name__)


def create_celery() -> Celery:
    """Create and configure Celery instance."""
    
    celery_app = Celery("worker")
    
    # Configure Celery
    celery_app.conf.broker_url = settings.CELERY_BROKER_URL
    celery_app.conf.result_backend = settings.REDIS_URI
    
    # Task serialization format
    celery_app.conf.task_serializer = "json"
    celery_app.conf.result_serializer = "json"
    celery_app.conf.accept_content = ["json"]
    
    # Enable UTC timezone
    celery_app.conf.enable_utc = True
    
    # Task execution settings
    celery_app.conf.worker_prefetch_multiplier = 1
    celery_app.conf.task_acks_late = True
    
    # Configure logging
    celery_app.conf.worker_log_color = False
    celery_app.conf.worker_redirect_stdouts = False
    
    # Import tasks modules
    celery_app.autodiscover_tasks(["app.tasks"])
    
    # Configure scheduled tasks (beat)
    celery_app.conf.beat_schedule = {
        "process-scheduled-workflows": {
            "task": "app.tasks.executions.process_scheduled_workflows_task",
            "schedule": crontab(minute="*"),  # Run every minute
            "options": {"expires": 55}  # Task expires if not started within 55 seconds
        },
        "cleanup-old-executions": {
            "task": "app.tasks.executions.cleanup_old_executions_task",
            "schedule": crontab(hour="*/12"),  # Run every 12 hours
            "options": {"expires": 3600}
        },
    }
    
    return celery_app


# Create a base Celery task class with async support
class AsyncTask:
    """Base class for async Celery tasks."""
    
    @staticmethod
    def get_db():
        """Get database session."""
        db = SessionLocal()
        try:
            return db
        finally:
            db.close()
    
    @staticmethod
    def run_async(async_func, *args, **kwargs):
        """Run an async function from a sync context."""
        # Get event loop or create a new one
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(async_func(*args, **kwargs))


# Create Celery app instance
celery_app = create_celery()
