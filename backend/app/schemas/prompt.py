# app/schemas/prompt.py

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
from uuid import UUID
from datetime import datetime


class ParameterSchema(BaseModel):
    """Schema for a detected parameter"""
    name: str
    description: str
    default: Optional[Union[str, int, float, bool, None]] = None
    required: bool = True


class OptimizePromptRequest(BaseModel):
    """Request schema for optimize-prompt endpoint"""
    prompt: str


class OptimizePromptResponse(BaseModel):
    """Response schema for optimize-prompt endpoint"""
    original_prompt: str
    optimized_prompt: str
    parameters: List[Dict[str, Any]] = []  # Use Dict instead of ParameterSchema for more flexibility


class RoutePromptRequest(BaseModel):
    """Request schema for route-prompt endpoint"""
    prompt: str


class RoutePromptResponse(BaseModel):
    """Response schema for route-prompt endpoint"""
    prompt: str
    needs_reasoning: bool


class PromptCreate(BaseModel):
    """Schema for creating a new prompt record"""
    original_prompt: str
    optimized_prompt: str
    needs_reasoning: bool


class PromptResponse(BaseModel):
    """Schema for returning a prompt record"""
    id: UUID
    user_id: str
    original_prompt: str
    optimized_prompt: str
    needs_reasoning: str
    created_at: datetime
    
    class Config:
        orm_mode = True