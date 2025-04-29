from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, and_

from app.api.deps import get_db, get_current_user, require_admin
from app.models import AuditLog
from app.schemas.audit import (
    AuditLogResponse,
    AuditLogListResponse
)

router = APIRouter()

@router.get(
    "/", 
    response_model=AuditLogListResponse,
    summary="List audit logs",
    dependencies=[Depends(require_admin)]
)
async def list_audit_logs(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    event_type: Optional[str] = None,
    user_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    resource_id: Optional[str] = None,
    current_user = Depends(get_current_user)
):
    """
    List audit logs with optional filtering.
    Admin access required.
    """
    # Build query
    query = select(AuditLog)
    
    # Apply filters
    filters = []
    if event_type:
        filters.append(AuditLog.event_type == event_type)
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if start_time:
        filters.append(AuditLog.timestamp >= start_time)
    if end_time:
        filters.append(AuditLog.timestamp <= end_time)
    if resource_id:
        # This assumes resource_id is a top-level key in the resource_data JSON
        filters.append(AuditLog.resource_data.contains({"id": resource_id}))
    
    if filters:
        query = query.filter(and_(*filters))
    
    # Get total count
    count_query = select(AuditLog)
    if filters:
        count_query = count_query.filter(and_(*filters))
    
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())
    
    # Apply pagination and ordering
    query = query.order_by(desc(AuditLog.timestamp)).offset(skip).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    audit_logs = result.scalars().all()
    
    return {
        "total": total,
        "items": list(audit_logs),
        "skip": skip,
        "limit": limit
    }

@router.get(
    "/{log_id}", 
    response_model=AuditLogResponse,
    summary="Get an audit log by ID",
    dependencies=[Depends(require_admin)]
)
async def get_audit_log(
    log_id: str = Path(..., title="The ID of the audit log to get"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get an audit log by ID.
    Admin access required.
    """
    result = await db.execute(select(AuditLog).filter(AuditLog.id == log_id))
    audit_log = result.scalars().first()
    
    if not audit_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit log with ID {log_id} not found"
        )
    
    return audit_log