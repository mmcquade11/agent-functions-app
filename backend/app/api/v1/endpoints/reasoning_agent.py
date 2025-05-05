from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.auth import get_current_user
from app.services.llm_wrappers import call_openai_o3_reasoning
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class PromptPayload(BaseModel):
    prompt: str

@router.post("/reasoning-agent")
async def reasoning_agent(payload: PromptPayload, user=Depends(get_current_user)):
    """
    Process a prompt through the reasoning agent to break down complex tasks.
    """
    logger.info(f"Reasoning agent called with: {payload.prompt[:100]}...")
    
    try:
        # Call the reasoning chain with the user's prompt
        reasoning_steps = await call_openai_o3_reasoning(payload.prompt)
        
        logger.info(f"Reasoning agent response: {reasoning_steps[:100]}...")
        return {"reasoned_prompt": reasoning_steps}
    except Exception as e:
        logger.error(f"Error in reasoning agent: {str(e)}")
        # Return a helpful error message that still moves the conversation forward
        error_message = (
            "I'm having trouble processing your request right now. "
            "Could you try providing more details about what you're trying to accomplish? "
            "For example, what specific tools or data sources do you need to work with?"
        )
        return {"reasoned_prompt": error_message}