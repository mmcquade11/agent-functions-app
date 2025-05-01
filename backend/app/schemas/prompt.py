# app/schemas/prompt.py
from typing import Optional
from pydantic import BaseModel
from uuid import UUID


class RoutePromptRequest(BaseModel):
    prompt: str

class RoutePromptResponse(BaseModel):
    prompt: str
    needs_reasoning: bool

class OptimizePromptRequest(BaseModel):
    prompt: str

class OptimizePromptResponse(BaseModel):
    original_prompt: str
    optimized_prompt: str

class PromptCreate(BaseModel):
    original_prompt: str
    optimized_prompt: str
    needs_reasoning: bool

class PromptResponse(PromptCreate):
    id: UUID
    user_id: str

    class Config:
        orm_mode = True
