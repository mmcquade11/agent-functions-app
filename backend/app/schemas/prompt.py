# app/schemas/prompt.py

from pydantic import BaseModel

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
