from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete

from app.api.deps import get_db, get_current_user
from app.models import Workflow
from app.schemas.workflow import (
    WorkflowCreate, 
    WorkflowUpdate, 
    WorkflowResponse, 
    WorkflowListResponse
)
from app.services.audit import log_audit_event

router = APIRouter()

@router.post(
    "/", 
    response_model=WorkflowResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workflow"
)
async def create_workflow(
    workflow: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new workflow.
    """
    # Create new workflow object
    new_workflow = Workflow(
        name=workflow.name,
        description=workflow.description,
        workflow_definition=workflow.workflow_definition.dict(),
        is_active=workflow.is_active,
        is_scheduled=workflow.is_scheduled,
        created_by=current_user.sub
    )
    
    # Add to database
    db.add(new_workflow)
    await db.commit()
    await db.refresh(new_workflow)
    
    # Log audit event
    await log_audit_event(
        db, 
        "workflow.create", 
        current_user.sub, 
        {"workflow_id": str(new_workflow.id), "workflow_name": new_workflow.name}
    )
    
    return new_workflow

from app.schemas.workflow import WorkflowResponse

@router.get(
    "/", 
    response_model=WorkflowListResponse,
    summary="List workflows"
)
async def list_workflows(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    name: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_scheduled: Optional[bool] = None,
    current_user = Depends(get_current_user)
):
    """
    List all workflows with optional filtering.
    """
    # Build query
    query = select(Workflow)
    
    # Apply filters
    if name:
        query = query.filter(Workflow.name.ilike(f"%{name}%"))
    if is_active is not None:
        query = query.filter(Workflow.is_active == is_active)
    if is_scheduled is not None:
        query = query.filter(Workflow.is_scheduled == is_scheduled)
    
    # Get total count
    count_query = select(Workflow)
    if name:
        count_query = count_query.filter(Workflow.name.ilike(f"%{name}%"))
    if is_active is not None:
        count_query = count_query.filter(Workflow.is_active == is_active)
    if is_scheduled is not None:
        count_query = count_query.filter(Workflow.is_scheduled == is_scheduled)
    
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(Workflow.created_at.desc())
    
    # Execute query
    result = await db.execute(query)
    workflows = result.scalars().all()

    # 🚀 Map ORM -> Pydantic models here
    workflows_response = []
    for workflow in workflows:
        workflows_response.append(
            WorkflowResponse.from_orm(workflow)
        )  
    
    return {
        "total": total,
        "items": workflows_response,
        "skip": skip,
        "limit": limit
    }

@router.get(
    "/{workflow_id}", 
    response_model=WorkflowResponse,
    summary="Get a workflow by ID"
)
async def get_workflow(
    workflow_id: str = Path(..., title="The ID of the workflow to get"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get a workflow by ID.
    """
    result = await db.execute(select(Workflow).filter(Workflow.id == workflow_id))
    workflow = result.scalars().first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    
    return workflow

@router.put(
    "/{workflow_id}", 
    response_model=WorkflowResponse,
    summary="Update a workflow"
)
async def update_workflow(
    workflow_update: WorkflowUpdate,
    workflow_id: str = Path(..., title="The ID of the workflow to update"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update a workflow.
    """
    # Check if workflow exists
    result = await db.execute(select(Workflow).filter(Workflow.id == workflow_id))
    workflow = result.scalars().first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    
    # Prepare update data
    update_data = workflow_update.dict(exclude_unset=True)
    
    # If workflow_definition is provided, convert it to a dict
    if "workflow_definition" in update_data:
        update_data["workflow_definition"] = update_data["workflow_definition"].dict()
    
    # Update workflow
    for key, value in update_data.items():
        setattr(workflow, key, value)
    
    await db.commit()
    await db.refresh(workflow)
    
    # Log audit event
    await log_audit_event(
        db, 
        "workflow.update", 
        current_user.sub, 
        {"workflow_id": str(workflow.id), "workflow_name": workflow.name}
    )
    
    return workflow

@router.delete(
    "/{workflow_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a workflow"
)
async def delete_workflow(
    workflow_id: str = Path(..., title="The ID of the workflow to delete"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Delete a workflow.
    """
    # Check if workflow exists
    result = await db.execute(select(Workflow).filter(Workflow.id == workflow_id))
    workflow = result.scalars().first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    
    # Get workflow name for audit log
    workflow_name = workflow.name
    
    # Delete workflow
    await db.delete(workflow)
    await db.commit()
    
    # Log audit event
    await log_audit_event(
        db, 
        "workflow.delete", 
        current_user.sub, 
        {"workflow_id": workflow_id, "workflow_name": workflow_name}
    )
    
    return None