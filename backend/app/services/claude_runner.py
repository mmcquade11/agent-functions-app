# app/services/enhanced_claude_runner.py

import asyncio
import logging
from anthropic import AsyncAnthropic
from app.services.tool_registry import ToolRegistry
from typing import AsyncGenerator, Dict, Any, List, Optional
from app.core.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load API key from environment variables via settings
claude = AsyncAnthropic(api_key=settings.CLAUDE_API_KEY)

async def stream_enhanced_claude(
    prompt: str, 
    tool_registry: ToolRegistry,
    needs_reasoning: bool = False,
    system_prompt: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 4000
) -> AsyncGenerator[dict, None]:
    """
    Stream Claude's responses with enhanced handling for both native and custom integrations.
    
    Args:
        prompt: The user prompt (optimized version)
        tool_registry: Registry of available tools
        needs_reasoning: Whether this prompt requires reasoning
        system_prompt: Optional custom system prompt
        temperature: Sampling temperature (0-1)
        max_tokens: Maximum tokens in response
    """
    tools = tool_registry.get_tools_for_claude()
    
    # Use provided system prompt or create a default one
    if not system_prompt:
        system_prompt = (
            "You are an expert Python developer tasked with creating functional tool-using agents. "
            "Your job is to write Python code that solves the user's request using the available tools. "
            "Be sure to generate clean, efficient code with appropriate error handling. "
            "Prefer to use the tools available rather than suggesting external libraries when possible."
        )
        
        if needs_reasoning:
            system_prompt += (
                " This task requires careful reasoning and analysis. "
                "Include detailed comments explaining your approach and why certain decisions were made. "
                "Be thorough in your implementation with proper error handling and edge case coverage."
            )
        else:
            system_prompt += (
                " Generate concise code that directly addresses the task. "
                "Focus on clarity and efficiency in your implementation."
            )
    
    # Debug info
    logger.info(f"🔵 Streaming Claude response for prompt: {prompt[:100]}...")
    logger.info(f"🔵 Reasoning flag: {needs_reasoning}")
    logger.info(f"🔵 Using system prompt: {system_prompt[:100]}...")
    logger.info(f"🔵 Available tools: {[t['name'] for t in tools]}")
    
    # Helper function to handle tool usage with detailed debugging
    async def handle_tool_use(message_id, tool_name, tool_input):
        logger.info(f"🛠️ Tool use: {tool_name} with input: {tool_input}")
        
        try:
            # Execute the tool with the provided input
            result = tool_registry.run_tool(tool_name, tool_input)
            logger.info(f"🛠️ Tool result: {result[:100]}...")
            
            # Return the tool result for streaming and to Claude
            return {
                "id": message_id,
                "tool": tool_name,
                "result": result
            }
        except Exception as e:
            error_message = f"Tool execution error: {str(e)}"
            logger.error(f"❌ {error_message}")
            return {
                "id": message_id,
                "tool": tool_name,
                "result": error_message,
                "error": str(e)
            }
    
    try:
        async with claude.messages.stream(
            model="claude-3-7-sonnet-20250219",
            messages=[{"role": "user", "content": prompt}],
            system=system_prompt,
            tools=tools,
            max_tokens=max_tokens,
            temperature=temperature,
        ) as stream:
            async for message in stream:
                # Handle different message types from Claude
                if message.type == "message_start":
                    yield {"phase": "claude", "type": "start"}
                
                elif message.type == "content_block_delta":
                    # Handle text output
                    if hasattr(message.delta, "text") and message.delta.text:
                        yield {"phase": "claude", "type": "text", "content": message.delta.text}
                    
                    # Handle tool use deltas if present
                    elif hasattr(message.delta, "tool_use") and message.delta.tool_use:
                        logger.debug(f"🛠️ Tool use delta: {message.delta.tool_use}")
                
                elif message.type == "tool_use":
                    # Complete tool use message received
                    tool_name = message.name
                    tool_input = message.input
                    
                    # Yield tool use event to frontend
                    yield {
                        "phase": "claude", 
                        "type": "tool_use", 
                        "tool": tool_name, 
                        "input": tool_input
                    }
                    
                    # Execute the tool and get result
                    tool_result = await handle_tool_use(message.id, tool_name, tool_input)
                    
                    # Yield tool result for frontend
                    yield {
                        "phase": "claude", 
                        "type": "tool_result", 
                        "tool": tool_name, 
                        "result": tool_result["result"]
                    }
                    
                    # Send result back to Claude
                    await stream.send_tool_result(
                        tool_use_id=tool_result["id"], 
                        content=tool_result["result"]
                    )
                
                elif message.type == "message_stop":
                    logger.info("🏁 Claude message complete")
                    yield {"phase": "claude", "type": "done"}
    
    except Exception as e:
        logger.error(f"❌ Error in Claude stream: {str(e)}")
        yield {"phase": "claude", "type": "error", "content": f"Error: {str(e)}"}
        yield {"phase": "claude", "type": "done"}

# Alias for backward compatibility
stream_claude_tool_use = stream_enhanced_claude