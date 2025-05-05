# app/agents/reasoning_agent.py
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional, Any, AsyncGenerator
import asyncio
import json
import logging
from datetime import datetime

from app.db.session import get_db
from app.core.auth import get_current_user
# Remove User import since it doesn't exist
# from app.models.user import User
from app.models.prompt import Prompt
from app.services.llm_wrappers import call_openai_o3_reasoning
from app.services.claude_runner import stream_claude_tool_use
from app.services.tool_registry import ToolRegistry
from app.services.tool_init import registry

logger = logging.getLogger(__name__)

class ReasoningAgent:
    def __init__(
        self,
        db: AsyncSession,
        user_id: str,
        tool_registry: ToolRegistry,
    ):
        self.db = db
        self.user_id = user_id
        self.tool_registry = tool_registry
        self.prompt_id = None

    async def initialize_prompt_record(self, original_prompt: str, optimized_prompt: str) -> None:
        """Create a new prompt record in the database"""
        from uuid import uuid4
        from app.models.prompt import Prompt
        
        prompt = Prompt(
            id=uuid4(),
            user_id=self.user_id,
            original_prompt=original_prompt,
            optimized_prompt=optimized_prompt,
            needs_reasoning="true"
        )
        self.db.add(prompt)
        await self.db.commit()
        await self.db.refresh(prompt)
        self.prompt_id = prompt.id

    async def execute(self, original_prompt: str, optimized_prompt: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute a query using the reasoning agent approach"""
        await self.initialize_prompt_record(original_prompt, optimized_prompt)
        
        # Step 1: Generate a reasoning plan
        planning_prompt = f"""
        Task: {optimized_prompt}
        
        You are a reasoning agent that carefully plans before acting.
        Think step by step about how to approach this task.
        Break down the problem, consider what tools might be needed, and outline a clear plan of action.
        """
        
        try:
            planning_response = await call_openai_o3_reasoning(planning_prompt)
            plan = planning_response
            
            yield {"phase": "reasoning", "type": "plan", "content": plan}
            
            # Step 2: Extract required tools based on the plan
            tool_extraction_prompt = f"""
            Based on this reasoning plan:
            
            {plan}
            
            List the specific tools needed to execute this plan. 
            Format your response as a JSON array of tool names.
            Available tools: {', '.join(self.tool_registry.list_tools())}
            """
            
            tools_response = await call_openai_o3_reasoning(tool_extraction_prompt)
            
            # Try to extract tool names from the response
            try:
                # Look for anything that might be a JSON array
                import re
                json_match = re.search(r'\[.*?\]', tools_response)
                if json_match:
                    json_str = json_match.group(0)
                    required_tools = json.loads(json_str)
                    # Validate that all tools exist
                    required_tools = [t for t in required_tools if self.tool_registry.has_tool(t)]
                else:
                    # Fallback to all tools
                    required_tools = self.tool_registry.list_tools()
            except:
                # Fallback in case of parsing issues
                required_tools = self.tool_registry.list_tools()
            
            yield {"phase": "reasoning", "type": "tools", "content": required_tools}
            
            # Step 3: Execute the plan using Claude with selected tools
            execution_prompt = f"""
            Original task: {optimized_prompt}
            
            Here is a carefully reasoned plan to solve this task:
            
            {plan}
            
            Please execute this plan step by step, using the available tools when necessary.
            Show your work clearly at each step.
            """
            
            # Stream Claude's execution
            async for chunk in stream_claude_tool_use(execution_prompt, self.tool_registry, needs_reasoning=True):
                yield chunk
            
            # Step 4: Reflection (optional)
            reflection_prompt = f"""
            Original task: {optimized_prompt}
            
            Reflect on the execution. What went well? What could be improved?
            Did the execution solve the original task effectively?
            """
            
            reflection_response = await call_openai_o3_reasoning(reflection_prompt)
            yield {"phase": "reasoning", "type": "reflection", "content": reflection_response}
            
        except Exception as e:
            logger.error(f"Error in reasoning agent: {str(e)}")
            yield {"phase": "error", "type": "error", "content": f"Error executing reasoning agent: {str(e)}"}

# Create a streaming endpoint for the reasoning agent
async def stream_reasoning_agent(
    original_prompt: str,
    optimized_prompt: str,
    db: AsyncSession,
    user_id: str,
) -> AsyncGenerator[Dict[str, Any], None]:
    agent = ReasoningAgent(
        db=db,
        user_id=user_id,
        tool_registry=registry,
    )
    
    async for chunk in agent.execute(original_prompt, optimized_prompt):
        yield chunk