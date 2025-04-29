from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime

class AuditLogCreate(BaseModel):
    event_type: str
    user_id: str
    resource_data: Dict
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class AuditLogResponse(BaseModel):
    id: str
    timestamp: datetime
    event_type: str
    user_id: str
    resource_data: Dict
    ip_address: Optional[str]
    user_agent: Optional[str]

class AuditLogListResponse(BaseModel):
    total: int
    items: List[AuditLogResponse]
    skip: int
    limit: int

