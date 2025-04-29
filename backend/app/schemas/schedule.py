from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime

class ScheduleCreate(BaseModel):
    workflow_id: str
    cron_expression: str
    execution_inputs: Optional[Dict] = {}
    timezone: str = "UTC"
    is_active: bool = True
    name: Optional[str] = None
    description: Optional[str] = None

class ScheduleUpdate(BaseModel):
    cron_expression: Optional[str] = None
    execution_inputs: Optional[Dict] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None
    name: Optional[str] = None
    description: Optional[str] = None

class ScheduleResponse(BaseModel):
    id: str
    workflow_id: str
    cron_expression: str
    is_active: bool
    name: Optional[str]
    description: Optional[str]
    created_by: str
    created_at: datetime
    updated_at: datetime
    execution_inputs: Dict
    timezone: str

class ScheduleListResponse(BaseModel):
    total: int
    items: List[ScheduleResponse]
    skip: int
    limit: int    
