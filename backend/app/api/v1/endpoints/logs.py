from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from sse_starlette.sse import EventSourceResponse
import json
import asyncio

from app.api.deps import get_db, get_current_user
from app.models import ExecutionLog, WorkflowExecution
from app.schemas.logs import (
    LogResponse,
    LogListResponse
)
from app.websockets.manager import websocket_manager

router = APIRouter()

@router.get(
    "/executions/{execution_id}/logs", 
    response_model=LogListResponse,
    summary="Get execution logs"
)
async def get_execution_logs(
    execution_id: str = Path(..., title="The ID of the execution"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    level: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get logs for a workflow execution.
    """
    # Check if execution exists
    execution_result = await db.execute(
        select(WorkflowExecution).filter(WorkflowExecution.id == execution_id)
    )
    execution = execution_result.scalars().first()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution with ID {execution_id} not found"
        )
    
    # Build query
    query = select(ExecutionLog).filter(ExecutionLog.execution_id == execution_id)
    
    # Apply level filter
    if level:
        query = query.filter(ExecutionLog.level == level.upper())
    
    # Get total count
    count_query = select(ExecutionLog).filter(ExecutionLog.execution_id == execution_id)
    if level:
        count_query = count_query.filter(ExecutionLog.level == level.upper())
    
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())
    
    # Apply pagination and ordering
    query = query.order_by(ExecutionLog.timestamp.desc()).offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return {
        "total": total,
        "items": list(logs),
        "skip": skip,
        "limit": limit
    }

@router.get(
    "/executions/{execution_id}/logs/stream", 
    summary="Stream execution logs as Server-Sent Events"
)
async def stream_execution_logs(
    request: Request,
    execution_id: str = Path(..., title="The ID of the execution"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Stream logs for a workflow execution using Server-Sent Events (SSE).
    """
    # Check if execution exists
    execution_result = await db.execute(
        select(WorkflowExecution).filter(WorkflowExecution.id == execution_id)
    )
    execution = execution_result.scalars().first()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution with ID {execution_id} not found"
        )
    
    async def event_generator():
        # Send recent logs first
        recent_logs_query = (
            select(ExecutionLog)
            .filter(ExecutionLog.execution_id == execution_id)
            .order_by(ExecutionLog.timestamp)
            .limit(100)
        )
        recent_logs_result = await db.execute(recent_logs_query)
        recent_logs = recent_logs_result.scalars().all()
        
        for log in recent_logs:
            # Convert log to dict
            log_data = {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "level": log.level,
                "message": log.message,
                "step_id": log.step_id,
                "step_name": log.step_name,
                "metadata": log.log_metadata
            }
            yield {
                "event": "log",
                "data": json.dumps(log_data)
            }
        
        # Create a queue for new logs
        queue = asyncio.Queue()
        
        # Register the queue with the web socket manager
        # Note: This is a simplified approach. In a real implementation,
        # you would need to implement a proper pub/sub system.
        
        # Keep the connection open and send new logs as they arrive
        try:
            while True:
                # In a real implementation, you would wait for new logs
                # For now, we'll just sleep and check for client disconnection
                if await request.is_disconnected():
                    break
                
                # Sleep to avoid busy waiting
                await asyncio.sleep(1)
                
                # Check for new logs
                # This is a placeholder. In a real implementation,
                # you would use a proper message queue or pub/sub system.
                
        except asyncio.CancelledError:
            # Client disconnected
            pass
    
    return EventSourceResponse(event_generator())