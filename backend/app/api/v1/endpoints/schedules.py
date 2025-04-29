from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, or_, and_
from croniter import croniter

from app.api.deps import get_db, get_current_user
from app.models import WorkflowSchedule, Workflow
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    ScheduleListResponse
)
from app.services.audit import log_audit_event

router = APIRouter()

@router.post(
    "/workflows/{workflow_id}/schedules", 
    response_model=ScheduleResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new schedule"
)
async def create_schedule(
    schedule: ScheduleCreate,
    workflow_id: str = Path(..., title="The ID of the workflow"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new schedule for a workflow.
    """
    # Check if workflow exists
    result = await db.execute(select(Workflow).filter(Workflow.id == workflow_id))
    workflow = result.scalars().first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    
    # Validate cron expression
    if not croniter.is_valid(schedule.cron_expression):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid cron expression: {schedule.cron_expression}"
        )
    
    # Create new schedule
    new_schedule = WorkflowSchedule(
        workflow_id=workflow_id,
        cron_expression=schedule.cron_expression,
        name=schedule.name,
        description=schedule.description,
        is_active=schedule.is_active,
        created_by=current_user.sub,
        execution_inputs=schedule.execution_inputs,
        timezone=schedule.timezone
    )
    
    # Add to database
    db.add(new_schedule)
    await db.commit()
    await db.refresh(new_schedule)
    
    # Update workflow is_scheduled flag if needed
    if new_schedule.is_active and not workflow.is_scheduled:
        workflow.is_scheduled = True
        await db.commit()
    
    # Log audit event
    await log_audit_event(
        db, 
        "workflow.schedule.create", 
        current_user.sub, 
        {
            "workflow_id": workflow_id,
            "schedule_id": str(new_schedule.id),
            "schedule_name": new_schedule.name
        }
    )
    
    return new_schedule

@router.get(
    "/schedules", 
    response_model=ScheduleListResponse,
    summary="List schedules"
)
async def list_schedules(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    workflow_id: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user = Depends(get_current_user)
):
    """
    List all schedules with optional filtering.
    """
    # Build query
    query = select(WorkflowSchedule)
    
    # Apply filters
    if workflow_id:
        query = query.filter(WorkflowSchedule.workflow_id == workflow_id)
    if is_active is not None:
        query = query.filter(WorkflowSchedule.is_active == is_active)
    
    # Get total count
    count_query = select(WorkflowSchedule)
    if workflow_id:
        count_query = count_query.filter(WorkflowSchedule.workflow_id == workflow_id)
    if is_active is not None:
        count_query = count_query.filter(WorkflowSchedule.is_active == is_active)
    
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(WorkflowSchedule.created_at.desc())
    
    # Execute query
    result = await db.execute(query)
    schedules = result.scalars().all()
    
    return {
        "total": total,
        "items": list(schedules),
        "skip": skip,
        "limit": limit
    }

@router.get(
    "/schedules/{schedule_id}", 
    response_model=ScheduleResponse,
    summary="Get a schedule by ID"
)
async def get_schedule(
    schedule_id: str = Path(..., title="The ID of the schedule to get"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get a schedule by ID.
    """
    result = await db.execute(
        select(WorkflowSchedule).filter(WorkflowSchedule.id == schedule_id)
    )
    schedule = result.scalars().first()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule with ID {schedule_id} not found"
        )
    
    return schedule

@router.put(
    "/schedules/{schedule_id}", 
    response_model=ScheduleResponse,
    summary="Update a schedule"
)
async def update_schedule(
    schedule_update: ScheduleUpdate,
    schedule_id: str = Path(..., title="The ID of the schedule to update"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update a schedule.
    """
    # Check if schedule exists
    result = await db.execute(
        select(WorkflowSchedule).filter(WorkflowSchedule.id == schedule_id)
    )
    schedule = result.scalars().first()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule with ID {schedule_id} not found"
        )
    
    # Validate cron expression if provided
    if schedule_update.cron_expression is not None and not croniter.is_valid(schedule_update.cron_expression):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid cron expression: {schedule_update.cron_expression}"
        )
    
    # Prepare update data
    update_data = schedule_update.dict(exclude_unset=True)
    
    # Update schedule
    for key, value in update_data.items():
        setattr(schedule, key, value)
    
    await db.commit()
    await db.refresh(schedule)
    
    # Update workflow is_scheduled flag if needed
    if "is_active" in update_data:
        # Get all active schedules for this workflow
        active_schedules_query = select(WorkflowSchedule).filter(
            and_(
                WorkflowSchedule.workflow_id == schedule.workflow_id,
                WorkflowSchedule.is_active == True
            )
        )
        active_schedules_result = await db.execute(active_schedules_query)
        has_active_schedules = len(active_schedules_result.scalars().all()) > 0
        
        # Get the workflow
        workflow_result = await db.execute(
            select(Workflow).filter(Workflow.id == schedule.workflow_id)
        )
        workflow = workflow_result.scalars().first()
        
        if workflow and workflow.is_scheduled != has_active_schedules:
            workflow.is_scheduled = has_active_schedules
            await db.commit()
    
    # Log audit event
    await log_audit_event(
        db, 
        "workflow.schedule.update", 
        current_user.sub, 
        {
            "workflow_id": schedule.workflow_id,
            "schedule_id": schedule_id,
            "schedule_name": schedule.name
        }
    )
    
    return schedule

@router.delete(
    "/schedules/{schedule_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a schedule"
)
async def delete_schedule(
    schedule_id: str = Path(..., title="The ID of the schedule to delete"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Delete a schedule.
    """
    # Check if schedule exists
    result = await db.execute(
        select(WorkflowSchedule).filter(WorkflowSchedule.id == schedule_id)
    )
    schedule = result.scalars().first()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule with ID {schedule_id} not found"
        )
    
    # Store workflow_id for later use
    workflow_id = schedule.workflow_id
    was_active = schedule.is_active
    
    # Delete schedule
    await db.delete(schedule)
    await db.commit()
    
    # Update workflow is_scheduled flag if needed
    if was_active:
        # Check if workflow has any other active schedules
        active_schedules_query = select(WorkflowSchedule).filter(
            and_(
                WorkflowSchedule.workflow_id == workflow_id,
                WorkflowSchedule.is_active == True
            )
        )
        active_schedules_result = await db.execute(active_schedules_query)
        has_active_schedules = len(active_schedules_result.scalars().all()) > 0
        
        # Get the workflow
        workflow_result = await db.execute(
            select(Workflow).filter(Workflow.id == workflow_id)
        )
        workflow = workflow_result.scalars().first()
        
        if workflow and workflow.is_scheduled and not has_active_schedules:
            workflow.is_scheduled = False
            await db.commit()
    
    # Log audit event
    await log_audit_event(
        db, 
        "workflow.schedule.delete", 
        current_user.sub, 
        {
            "workflow_id": workflow_id,
            "schedule_id": schedule_id
        }
    )
    
    return None