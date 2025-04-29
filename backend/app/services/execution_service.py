# backend/app/services/execution_service.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

async def get_workflow_execution(db: Session, execution_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a workflow execution by ID.
    """
    return {
        "id": execution_id,
        "workflow_id": "dummy-workflow-id",
        "status": "running"
    }

async def list_workflow_executions(
    db: Session,
    workflow_id: str,
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    List workflow executions for a workflow.
    """
    return {
        "total": 1,
        "items": [{
            "id": "dummy-execution-id",
            "workflow_id": workflow_id,
            "status": "running"
        }]
    }

async def cancel_workflow_execution(db: Session, execution_id: str, cancelled_by: str) -> Dict[str, Any]:
    """
    Cancel a running execution.
    """
    return {
        "id": execution_id,
        "status": "cancelled"
    }

async def get_execution_logs(
    db: Session,
    execution_id: str,
    skip: int = 0,
    limit: int = 100,
    level: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch logs for a workflow execution.
    """
    return {
        "total": 1,
        "items": [{
            "timestamp": "2025-04-25T18:30:00Z",
            "level": "INFO",
            "message": "Dummy log message",
            "step_id": "start",
            "step_name": "Start Node",
            "metadata": {}
        }]
    }
