# app/agents/regular_agent.py
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
from app.services.llm_wrappers import call_gpt_4o
from app.services.claude_runner import stream_claude_tool_use
from app.services.tool_registry import ToolRegistry
from app.services.tool_init import registry

logger = logging.getLogger(__name__)

class RegularAgent:
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
            needs_reasoning="false"
        )
        self.db.add(prompt)
        await self.db.commit()
        await self.db.refresh(prompt)
        self.prompt_id = prompt.id

    async def execute(self, original_prompt: str, optimized_prompt: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute a query using the regular agent approach (direct execution)"""
        await self.initialize_prompt_record(original_prompt, optimized_prompt)
        
        try:
            # Step 1: Optional task parsing/reformulation with GPT-4o
            system_prompt = """
            You are a task-oriented agent. Based on the user query below, extract the key request and format it clearly.
            If the request is already clear, simply return it with minimal changes.
            """
            
            formatted_query = await call_gpt_4o(system_prompt, optimized_prompt)
            
            yield {"phase": "optimize", "type": "formatted", "content": formatted_query}
            
            # Step 2: Direct execution with Claude using all available tools
            # Using all tools by default for regular agent to reduce complexity
            all_tools = self.tool_registry.list_tools()
            
            # Stream Claude's execution
            async for chunk in stream_claude_tool_use(formatted_query, self.tool_registry, needs_reasoning=False):
                yield chunk
            
        except Exception as e:
            logger.error(f"Error in regular agent: {str(e)}")
            yield {"phase": "error", "type": "error", "content": f"Error executing regular agent: {str(e)}"}

# Create a streaming endpoint for the regular agent
async def stream_regular_agent(
    original_prompt: str,
    optimized_prompt: str,
    db: AsyncSession,
    user_id: str,
) -> AsyncGenerator[Dict[str, Any], None]:
    agent = RegularAgent(
        db=db,
        user_id=user_id,
        tool_registry=registry,
    )
    
    async for chunk in agent.execute(original_prompt, optimized_prompt):
        yield chunk