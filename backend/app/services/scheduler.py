import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

import pytz
from croniter import croniter
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.workflow import WorkflowSchedule, Workflow

from app.core.config import settings
from app.db.session import get_db
from app.models import Workflow, WorkflowExecution, WorkflowSchedule, ExecutionLog
from app.services.executor import execute_workflow

logger = logging.getLogger(__name__)


class SchedulerSettings(BaseModel):
    """Configuration settings for the Scheduler service."""
    scan_interval_seconds: int = 60
    timezone: str = "UTC"
    debug_mode: bool = False

async def process_scheduled_workflows(db_session):
    """
    Scan active workflow schedules and trigger executions if due.
    """
    result = await db_session.execute(
        select(WorkflowSchedule)
        .join(Workflow, WorkflowSchedule.workflow_id == Workflow.id)
        .where(
            WorkflowSchedule.is_active == True,
            Workflow.is_active == True
        )
    )
    schedules = result.scalars().all()

    # (Optional) Log how many schedules found
    print(f"[Scheduler] Found {len(schedules)} active schedules.")

    return schedules

class Scheduler:
    """
    Background Scheduler Service that manages scheduled workflow executions.
    
    This service periodically scans the database for scheduled workflows
    and triggers their execution when they're due to run.
    """
    
    def __init__(
        self, 
        settings: SchedulerSettings = None,
        db_session_factory=get_db
    ):
        """
        Initialize the Scheduler service.
        
        Args:
            settings: Configuration settings for the scheduler
            db_session_factory: Factory function to create database sessions
        """
        self.settings = settings or SchedulerSettings()
        self.db_session_factory = db_session_factory
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
        self.stop_event = asyncio.Event()
        
        logger.info(
            f"Scheduler initialized with scan interval of {self.settings.scan_interval_seconds} seconds"
        )
    
    async def start(self):
        """Start the scheduler background task."""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        logger.info("Starting workflow scheduler")
        self.is_running = True
        self.stop_event.clear()
        self.task = asyncio.create_task(self._run_scheduler_loop())
    
    async def stop(self):
        """Stop the scheduler background task."""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return
        
        logger.info("Stopping workflow scheduler")
        self.is_running = False
        self.stop_event.set()
        
        if self.task:
            try:
                await asyncio.wait_for(self.task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Scheduler task did not terminate gracefully, cancelling")
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    logger.info("Scheduler task cancelled")
            
            self.task = None
    
    async def _run_scheduler_loop(self):
        """Run the main scheduler loop that processes scheduled workflows."""
        while not self.stop_event.is_set():
            try:
                await self._process_scheduled_workflows()
            except Exception as e:
                logger.exception(f"Error in scheduler loop: {str(e)}")
            
            # Wait for the next scan interval or until stop_event is set
            try:
                await asyncio.wait_for(
                    self.stop_event.wait(),
                    timeout=self.settings.scan_interval_seconds
                )
            except asyncio.TimeoutError:
                # This is expected when the timeout occurs and we should continue
                pass
    
    async def _process_scheduled_workflows(self):
        """
        Process all active workflow schedules.
        
        This method scans the database for active schedules and
        executes workflows that are due to run.
        """
        async for db in self.db_session_factory():
            try:
                # Get all active schedules
                active_schedules = await self._get_active_schedules(db)
                
                if self.settings.debug_mode:
                    logger.debug(f"Found {len(active_schedules)} active schedules")
                
                # Process each schedule
                for schedule in active_schedules:
                    try:
                        await self._process_schedule(db, schedule)
                    except Exception as e:
                        logger.error(
                            f"Error processing schedule {schedule.id}: {str(e)}",
                            exc_info=self.settings.debug_mode
                        )
            except Exception as e:
                logger.exception(f"Error fetching scheduled workflows: {str(e)}")
    
    async def _get_active_schedules(self, db: AsyncSession) -> List[WorkflowSchedule]:
        """
        Get all active workflow schedules.
        
        Args:
            db: Database session
            
        Returns:
            List of active WorkflowSchedule instances
        """
        # Query for active schedules with active workflows
        stmt = (
            select(WorkflowSchedule)
            .join(Workflow, WorkflowSchedule.workflow_id == Workflow.id)
            .where(
                and_(
                    WorkflowSchedule.is_active == True,
                    Workflow.is_active == True
                )
            )
        )
        
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def _process_schedule(self, db: AsyncSession, schedule: WorkflowSchedule):
        """
        Process a single workflow schedule.
        
        Args:
            db: Database session
            schedule: The WorkflowSchedule to process
        """
        # Get current time in the schedule's timezone
        current_time = datetime.now(pytz.timezone(schedule.timezone))
        
        # Create a croniter instance to calculate the previous scheduled time
        try:
            cron = croniter(schedule.cron_expression, current_time)
            prev_time = cron.get_prev(datetime)
            next_time = cron.get_next(datetime)
        except Exception as e:
            logger.error(
                f"Invalid cron expression '{schedule.cron_expression}' for schedule {schedule.id}: {str(e)}"
            )
            return
        
        # Calculate time difference in seconds between now and the previous run time
        time_diff_seconds = (current_time - prev_time).total_seconds()
        
        # If the previous run time is within the scan interval, we should run this workflow
        # Using a small buffer to account for scheduler timing variations
        if 0 <= time_diff_seconds <= (self.settings.scan_interval_seconds + 10):
            # Check if this schedule was already executed in this time window
            if await self._is_already_executed(db, schedule, prev_time):
                if self.settings.debug_mode:
                    logger.debug(
                        f"Schedule {schedule.id} already executed for {prev_time.isoformat()}"
                    )
                return
                
            # Execute the workflow
            await self._execute_scheduled_workflow(db, schedule, prev_time, next_time)
    
    async def _is_already_executed(
        self, 
        db: AsyncSession, 
        schedule: WorkflowSchedule, 
        scheduled_time: datetime
    ) -> bool:
        """
        Check if a schedule was already executed for the given time.
        
        Args:
            db: Database session
            schedule: The workflow schedule to check
            scheduled_time: The scheduled execution time
            
        Returns:
            True if the schedule was already executed, False otherwise
        """
        # Convert to UTC for database comparison
        scheduled_time_utc = scheduled_time.astimezone(pytz.UTC)
        
        # Calculate time window (with a small buffer to account for execution time variations)
        time_window_start = scheduled_time_utc.replace(
            second=0, microsecond=0
        )
        time_window_end = time_window_start.replace(
            minute=time_window_start.minute + 1
        )
        
        # Query for executions within this time window
        stmt = (
            select(WorkflowExecution)
            .where(
                and_(
                    WorkflowExecution.workflow_id == schedule.workflow_id,
                    WorkflowExecution.started_at >= time_window_start,
                    WorkflowExecution.started_at < time_window_end,
                    WorkflowExecution.executed_by == f"scheduler:{schedule.id}"
                )
            )
        )
        
        result = await db.execute(stmt)
        return result.first() is not None
    
    async def _execute_scheduled_workflow(
        self, 
        db: AsyncSession, 
        schedule: WorkflowSchedule, 
        scheduled_time: datetime,
        next_time: datetime
    ):
        """
        Execute a scheduled workflow.
        
        Args:
            db: Database session
            schedule: The workflow schedule to execute
            scheduled_time: The time this execution was scheduled for
            next_time: The next scheduled execution time
        """
        # Create execution record with scheduler as the executor
        inputs = schedule.execution_inputs or {}
        
        # Add schedule metadata to inputs
        inputs["_schedule"] = {
            "schedule_id": str(schedule.id),
            "scheduled_time": scheduled_time.isoformat(),
            "next_scheduled_time": next_time.isoformat(),
            "timezone": schedule.timezone
        }
        
        logger.info(
            f"Executing scheduled workflow {schedule.workflow_id} (schedule: {schedule.id})"
        )
        
        try:
            # Execute the workflow
            execution = await execute_workflow(
                db=db,
                workflow_id=schedule.workflow_id,
                inputs=inputs,
                executed_by=f"scheduler:{schedule.id}"
            )
            
            logger.info(
                f"Successfully scheduled workflow execution {execution.id} "
                f"for workflow {schedule.workflow_id}"
            )
            
            return execution
        except Exception as e:
            logger.error(
                f"Failed to execute scheduled workflow {schedule.workflow_id}: {str(e)}",
                exc_info=self.settings.debug_mode
            )
            raise


# Create a global scheduler instance that can be used throughout the application
scheduler = Scheduler()


# Function to start the scheduler when the application starts
async def start_scheduler():
    """Start the scheduler service."""
    await scheduler.start()


# Function to stop the scheduler when the application stops
async def stop_scheduler():
    """Stop the scheduler service."""
    await scheduler.stop()


# For use with FastAPI's lifespan manager
async def scheduler_lifespan():
    """
    Lifespan context manager for FastAPI.
    
    Usage:
        app = FastAPI(lifespan=scheduler_lifespan)
    """
    await start_scheduler()
    yield
    await stop_scheduler()

scheduler_instance = Scheduler()
