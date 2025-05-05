from typing import Optional
from pydantic import BaseModel
from uuid import UUID

class AgentRunRequest(BaseModel):
    prompt: str
    code: str

class AgentCreate(BaseModel):
    prompt_id: UUID
    name: str
    description: Optional[str]
    status: str = "draft"
    agent_code: str

class AgentResponse(AgentCreate):
    id: UUID
    user_id: str

    class Config:
        orm_mode = True

class PromptPayload(BaseModel):
    prompt: str       

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    agent_code: Optional[str] = None

    class Config:
        orm_mode = True

