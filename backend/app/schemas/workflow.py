from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator



class WorkflowStepBase(BaseModel):
    """Base model for workflow steps."""
    id: str = Field(..., description="Unique identifier for the step")
    name: str = Field(..., description="Display name for the step")
    type: str = Field(..., description="Type of step (e.g., 'http', 'script', 'condition')")
    config: Dict[str, Any] = Field(default_factory=dict, description="Configuration for the step")
    depends_on: List[str] = Field(default_factory=list, description="IDs of steps this step depends on")


class WorkflowDefinition(BaseModel):
    """Workflow definition model."""
    version: str = Field("1.0", description="Workflow definition version")
    steps: Optional[List[Dict]] = None
    connections: List[Dict[str, Any]] = Field(default_factory=list, description="Connections between steps")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Global workflow variables")
    
    @validator('steps')
    def validate_steps(cls, v):
        """Validate workflow steps."""
        if not v:
            raise ValueError("Workflow must have at least one step")
        
        # Check for unique step IDs
        step_ids = [step.get('id') for step in v if 'id' in step]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Step IDs must be unique")
            
        return v


class WorkflowBase(BaseModel):
    """Base model for workflow operations."""
    name: str = Field(..., description="Workflow name")
    description: Optional[str] = Field(None, description="Workflow description")
    workflow_definition: WorkflowDefinition = Field(..., description="Workflow definition")
    is_active: bool = Field(True, description="Whether the workflow is active")
    is_scheduled: bool = Field(False, description="Whether the workflow has scheduled executions")


class WorkflowCreate(WorkflowBase):
    """Model for creating a workflow."""
    pass


class WorkflowUpdate(BaseModel):
    """Model for updating a workflow."""
    name: Optional[str] = Field(None, description="Workflow name")
    description: Optional[str] = Field(None, description="Workflow description")
    workflow_definition: Optional[WorkflowDefinition] = Field(None, description="Workflow definition")
    is_active: Optional[bool] = Field(None, description="Whether the workflow is active")
    is_scheduled: Optional[bool] = Field(None, description="Whether the workflow has scheduled executions")


class WorkflowResponse(WorkflowBase):
    """Response model for workflow operations."""
    id: str = Field(..., description="Workflow ID")
    created_by: str = Field(..., description="User ID of creator")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class WorkflowListResponse(BaseModel):
    """Response model for listing workflows."""
    total: int = Field(..., description="Total number of workflows")
    items: List[WorkflowResponse] = Field(..., description="List of workflows")
    skip: int = Field(..., description="Number of workflows skipped")
    limit: int = Field(..., description="Maximum number of workflows returned")
