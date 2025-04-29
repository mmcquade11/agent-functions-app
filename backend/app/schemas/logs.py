from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

class LogCreate(BaseModel):
    execution_id: str
    level: str
    message: str
    step_id: Optional[str] = None
    step_name: Optional[str] = None
    log_metadata: Optional[Dict] = None

class LogResponse(BaseModel):
    id: int
    execution_id: str
    timestamp: datetime
    level: str
    message: str
    step_id: Optional[str]
    step_name: Optional[str]
    log_metadata: Optional[Dict]

class LogListResponse(BaseModel):
    total: int
    items: List[LogResponse]
    skip: int
    limit: int    
