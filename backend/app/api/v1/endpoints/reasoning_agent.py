from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.auth import get_current_user
from app.services.llm_wrappers import call_openai_o3_reasoning

router = APIRouter()

class PromptPayload(BaseModel):
    prompt: str

@router.post("/reasoning-agent")
async def reasoning_agent(payload: PromptPayload, user=Depends(get_current_user)):
    reasoning_steps = await call_openai_o3_reasoning(payload.prompt)
    return { "reasoned_prompt": reasoning_steps }
