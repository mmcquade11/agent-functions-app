from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from sqlalchemy import desc

from app.models.audit import AuditLog


async def log_audit_event(
    db: Session,
    event_type: str,
    user_id: str,
    resource_data: Dict[str, Any],
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AuditLog:
    """
    Log an audit event.
    
    Args:
        db: Database session
        event_type: Type of event (e.g., "workflow.create", "workflow.execution.start")
        user_id: ID of the user who performed the action
        resource_data: Data about the resource being acted upon
        ip_address: IP address of the user (optional)
        user_agent: User agent of the client (optional)
    
    Returns:
        The created audit log entry
    """
    audit_log = AuditLog(
        event_type=event_type,
        user_id=user_id,
        resource_data=resource_data,
        ip_address=ip_address,
        user_agent=user_agent,
        timestamp=datetime.utcnow()
    )
    
    db.add(audit_log)
    await db.flush()
    await db.commit()
    await db.refresh(audit_log)
    
    return audit_log


async def get_audit_logs(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    event_type: Optional[str] = None,
    user_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    resource_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get audit logs with filtering options.
    
    Args:
        db: Database session
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        event_type: Filter by event type (optional)
        user_id: Filter by user ID (optional)
        start_time: Filter by start time (optional)
        end_time: Filter by end time (optional)
        resource_id: Filter by resource ID (optional)
        
    Returns:
        Dictionary with total count and audit log entries
    """
    # Build query
    query = select(AuditLog)
    count_query = select(AuditLog)
    
    # Apply filters
    if event_type:
        query = query.where(AuditLog.event_type == event_type)
        count_query = count_query.where(AuditLog.event_type == event_type)
    
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
        count_query = count_query.where(AuditLog.user_id == user_id)
    
    if start_time:
        query = query.where(AuditLog.timestamp >= start_time)
        count_query = count_query.where(AuditLog.timestamp >= start_time)
    
    if end_time:
        query = query.where(AuditLog.timestamp <= end_time)
        count_query = count_query.where(AuditLog.timestamp <= end_time)
    
    if resource_id:
        # This requires a JSON query, implementation depends on the database
        # For PostgreSQL, you could use the -> operator
        # This is a simplification assuming resource_id is a top-level key
        query = query.where(AuditLog.resource_data.contains({"id": resource_id}))
        count_query = count_query.where(AuditLog.resource_data.contains({"id": resource_id}))
    
    # Execute count query
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())
    
    # Apply pagination and ordering
    query = query.order_by(desc(AuditLog.timestamp)).offset(skip).limit(limit)
    
    # Execute paginated query
    result = await db.execute(query)
    items = result.scalars().all()
    
    return {
        "total": total,
        "items": items
    }
