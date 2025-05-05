# app/agents/agent_router.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional, Any, AsyncGenerator, Union
import json
import logging

from app.db.session import get_db
from app.core.auth import get_current_user
# Remove User import since it doesn't exist
# from app.models.user import User
from app.models.prompt import Prompt
from app.services.tool_registry import ToolRegistry
from app.services.tool_init import registry
from app.agents.reasoning_agent import ReasoningAgent, stream_reasoning_agent
from app.agents.regular_agent import RegularAgent, stream_regular_agent

router = APIRouter()
logger = logging.getLogger(__name__)

# Function to decide whether to stream a response as text or JSON
async def process_agent_stream(
    stream_generator: AsyncGenerator[Dict[str, Any], None],
    as_json: bool = False
) -> AsyncGenerator[str, None]:
    async for chunk in stream_generator:
        if as_json:
            yield json.dumps(chunk) + "\n"
        else:
            # For text streaming, only yield the content
            if "content" in chunk:
                yield chunk["content"]

@router.post("/execute")
async def execute_agent(
    request: dict,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    as_json: bool = Query(False, description="Return results as JSON objects instead of text")
):
    """
    Execute an agent based on the needs_reasoning flag.
    This endpoint reads from sessionStorage values set by the frontend.
    """
    try:
        # Extract the original and optimized prompts from the request
        original_prompt = request.get("prompt", "")
        optimized_prompt = request.get("optimizedPrompt", original_prompt)
        needs_reasoning = request.get("needsReasoning", "false").lower() == "true"
        
        logger.info(f"Executing agent with reasoning={needs_reasoning}")
        logger.info(f"Original prompt: {original_prompt[:100]}...")
        logger.info(f"Optimized prompt: {optimized_prompt[:100]}...")
        
        # Choose the appropriate agent based on needs_reasoning
        if needs_reasoning:
            stream_generator = stream_reasoning_agent(
                original_prompt=original_prompt,
                optimized_prompt=optimized_prompt,
                db=db,
                user_id=current_user.sub
            )
        else:
            stream_generator = stream_regular_agent(
                original_prompt=original_prompt,
                optimized_prompt=optimized_prompt,
                db=db,
                user_id=current_user.sub
            )
        
        # Process the stream for either JSON or text output
        processed_stream = process_agent_stream(stream_generator, as_json)
        
        # Return a streaming response
        return StreamingResponse(
            processed_stream,
            media_type="text/event-stream" if as_json else "text/plain"
        )
    
    except Exception as e:
        logger.error(f"Error in agent execution: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")

@router.post("/test")
async def test_agent(
    request: dict,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Test mode for agents (non-streaming version)
    """
    try:
        # Extract the original and optimized prompts from the request
        original_prompt = request.get("prompt", "")
        optimized_prompt = request.get("optimizedPrompt", original_prompt)
        needs_reasoning = request.get("needsReasoning", "false").lower() == "true"
        
        logger.info(f"Testing agent with reasoning={needs_reasoning}")
        
        # For test mode, we'll return a simple success message
        return {
            "status": "tested",
            "message": f"Agent test successful. Using {'reasoning' if needs_reasoning else 'regular'} agent.",
            "details": {
                "original_prompt": original_prompt,
                "optimized_prompt": optimized_prompt,
                "needs_reasoning": needs_reasoning
            }
        }
    
    except Exception as e:
        logger.error(f"Error in agent test: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent test failed: {str(e)}")

@router.post("/schedule")
async def schedule_agent(
    request: dict,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Schedule an agent to run later
    """
    try:
        # Extract the original and optimized prompts from the request
        original_prompt = request.get("prompt", "")
        optimized_prompt = request.get("optimizedPrompt", original_prompt)
        needs_reasoning = request.get("needsReasoning", "false").lower() == "true"
        
        logger.info(f"Scheduling agent with reasoning={needs_reasoning}")
        
        # Here you would typically create a scheduled task
        # For now, we'll just pretend we scheduled it
        
        return {
            "status": "scheduled",
            "message": f"Agent has been scheduled. Using {'reasoning' if needs_reasoning else 'regular'} agent.",
            "schedule_id": "sample-schedule-id-123"
        }
    
    except Exception as e:
        logger.error(f"Error in agent scheduling: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent scheduling failed: {str(e)}")

# Export the router for FastAPI app registration
agents_router = router