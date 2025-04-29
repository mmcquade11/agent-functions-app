from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, or_, and_
import uuid


from app.api.deps import get_db, get_current_user
from app.models import WorkflowExecution, Workflow
from app.schemas.execution import (
    ExecutionCreate,
    ExecutionResponse,
    ExecutionListResponse
)
from app.services.executor import execute_workflow
from app.services.audit import log_audit_event
from app.tasks.executions import run_workflow_execution_task
from app.services.orchestrator import ExecutionOrchestrator
from app.schemas.execution import ExecuteAgentRequest, ExecuteAgentResponse


router = APIRouter()

@router.post(
    "/workflows/{workflow_id}/executions", 
    response_model=ExecutionResponse, 
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a workflow execution"
)
async def start_execution(
    background_tasks: BackgroundTasks,
    execution_data: ExecutionCreate,
    workflow_id: str = Path(..., title="The ID of the workflow to execute"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Start a workflow execution.
    """
    # Check if workflow exists
    result = await db.execute(select(Workflow).filter(Workflow.id == workflow_id))
    workflow = result.scalars().first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    
    if not workflow.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow with ID {workflow_id} is not active"
        )
    
    # Create execution record
    execution = await execute_workflow(
        db, 
        workflow_id, 
        execution_data.inputs or {}, 
        current_user.sub
    )
    
    # Start execution in background
    background_tasks.add_task(
        run_workflow_execution_task,
        execution_id=str(execution.id)
    )
    
    # Log audit event
    await log_audit_event(
        db, 
        "workflow.execution.start", 
        current_user.sub, 
        {
            "workflow_id": workflow_id,
            "workflow_name": workflow.name,
            "execution_id": str(execution.id)
        }
    )
    
    return execution

@router.get(
    "/workflows/{workflow_id}/executions", 
    response_model=ExecutionListResponse,
    summary="List workflow executions"
)
async def list_executions(
    workflow_id: str = Path(..., title="The ID of the workflow"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    List executions for a workflow.
    """
    # Check if workflow exists
    result = await db.execute(select(Workflow).filter(Workflow.id == workflow_id))
    workflow = result.scalars().first()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    
    # Build query
    query = select(WorkflowExecution).filter(WorkflowExecution.workflow_id == workflow_id)
    
    # Apply status filter
    if status:
        query = query.filter(WorkflowExecution.status == status)
    
    # Get total count
    count_query = select(WorkflowExecution).filter(WorkflowExecution.workflow_id == workflow_id)
    if status:
        count_query = count_query.filter(WorkflowExecution.status == status)
    
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(WorkflowExecution.started_at.desc())
    
    # Execute query
    result = await db.execute(query)
    executions = result.scalars().all()
    
    return {
        "total": total,
        "items": list(executions),
        "skip": skip,
        "limit": limit
    }

@router.get(
    "/executions/{execution_id}", 
    response_model=ExecutionResponse,
    summary="Get execution details"
)
async def get_execution(
    execution_id: str = Path(..., title="The ID of the execution"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get execution details.
    """
    result = await db.execute(
        select(WorkflowExecution).filter(WorkflowExecution.id == execution_id)
    )
    execution = result.scalars().first()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution with ID {execution_id} not found"
        )
    
    return execution

@router.post(
    "/executions/{execution_id}/cancel", 
    response_model=ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a workflow execution"
)
async def cancel_execution(
    execution_id: str = Path(..., title="The ID of the execution to cancel"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Cancel a running workflow execution.
    """
    result = await db.execute(
        select(WorkflowExecution).filter(WorkflowExecution.id == execution_id)
    )
    execution = result.scalars().first()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution with ID {execution_id} not found"
        )
    
    if execution.status not in ["pending", "running"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Execution with ID {execution_id} is not in a cancelable state"
        )
    
    # Update status to cancelled
    execution.status = "cancelled"
    execution.completed_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(execution)
    
    # Log audit event
    await log_audit_event(
        db, 
        "workflow.execution.cancel", 
        current_user.sub, 
        {
            "workflow_id": execution.workflow_id,
            "execution_id": execution_id
        }
    )
    
    return execution

@router.post("/execute-agent", response_model=ExecuteAgentResponse, status_code=status.HTTP_200_OK)
async def execute_agent(
    request: ExecuteAgentRequest,
    current_user=Depends(get_current_user),
):
    """
    Execute an agent based on optimized prompt and reasoning decision.
    """
    session_id = str(uuid.uuid4())

    orchestrator = ExecutionOrchestrator(session_id=session_id)  # ✅ No websocket manager passed manually

    try:
        await orchestrator.run_execution(
            prompt=request.prompt,
            needs_reasoning=request.needs_reasoning,
            user_arcee_token=request.user_arcee_token,
        )

        return ExecuteAgentResponse(
            status="success",
            message=f"Agent executed successfully. Session ID: {session_id}"
        )

    except Exception as e:
        return ExecuteAgentResponse(
            status="error",
            message=str(e)
        )
