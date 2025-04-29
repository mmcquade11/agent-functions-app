from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ExecutionCreate(BaseModel):
    """Model for creating a workflow execution."""
    inputs: Optional[Dict[str, Any]] = Field(None, description="Input parameters for the workflow")


class ExecutionResponse(BaseModel):
    """Response model for workflow executions."""
    id: str = Field(..., description="Execution ID")
    workflow_id: str = Field(..., description="ID of the associated workflow")
    status: str = Field(..., description="Execution status (pending, running, completed, failed, cancelled)")
    started_at: datetime = Field(..., description="Start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    execution_inputs: Optional[Dict[str, Any]] = Field(None, description="Input parameters")
    execution_outputs: Optional[Dict[str, Any]] = Field(None, description="Output results")
    error_message: Optional[str] = Field(None, description="Error message if execution failed")
    executed_by: str = Field(..., description="User ID or system that initiated the execution")
    
    class Config:
        from_attributes = True


class ExecutionListResponse(BaseModel):
    """Response model for listing executions."""
    total: int = Field(..., description="Total number of executions")
    items: List[ExecutionResponse] = Field(..., description="List of executions")
    skip: int = Field(..., description="Number of executions skipped")
    limit: int = Field(..., description="Maximum number of executions returned")


class ExecutionLogResponse(BaseModel):
    """Response model for execution logs."""
    id: int = Field(..., description="Log entry ID")
    execution_id: str = Field(..., description="ID of the associated execution")
    timestamp: datetime = Field(..., description="Log timestamp")
    level: str = Field(..., description="Log level (INFO, WARNING, ERROR, DEBUG)")
    message: str = Field(..., description="Log message")
    step_id: Optional[str] = Field(None, description="ID of the workflow step")
    step_name: Optional[str] = Field(None, description="Name of the workflow step")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    class Config:
        from_attributes = True


class ExecutionLogsResponse(BaseModel):
    """Response model for listing execution logs."""
    total: int = Field(..., description="Total number of log entries")
    items: List[ExecutionLogResponse] = Field(..., description="List of log entries")
    skip: int = Field(..., description="Number of log entries skipped")
    limit: int = Field(..., description="Maximum number of log entries returned")
    execution_id: str = Field(..., description="ID of the associated execution")

class ExecuteAgentRequest(BaseModel):
    """Request model for executing a dynamic agent."""
    prompt: str
    needs_reasoning: bool
    user_arcee_token: Optional[str] = None

class ExecuteAgentResponse(BaseModel):
    """Response model for executing a dynamic agent."""
    status: str
    message: str

