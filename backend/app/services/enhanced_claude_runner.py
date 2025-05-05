# app/services/enhanced_claude_runner.py

import asyncio
import logging
import json
import traceback
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
    request_id = f"req-{int(asyncio.get_event_loop().time() * 1000)}"
    tools = tool_registry.get_tools_for_claude()
    
    # Use provided system prompt or create a default one with improved instructions
    if not system_prompt:
        base_system_prompt = (
            "You are an expert Python developer tasked with creating functional tool-using agents. "
            "Your job is to write Python code that solves the user's request using the available tools. "
            "Be sure to generate clean, efficient code with appropriate error handling. "
            "Prefer to use the tools available rather than suggesting external libraries when possible. "
        )
        
        parameter_handling_instructions = (
            "\nIMPORTANT PARAMETER HANDLING INSTRUCTIONS:\n"
            "1. If you need specific parameters (like file IDs, emails, etc.), look for them in the user's request first.\n"
            "2. If critical parameters are missing, identify ALL needed parameters TOGETHER rather than asking one by one.\n"
            "3. For any missing but non-critical parameters, use reasonable defaults and document them in code comments.\n"
            "4. ALWAYS assume service account authentication for APIs unless explicitly told otherwise.\n"
            "5. When using placeholders, format them clearly as 'YOUR_PARAMETER_HERE' for easy identification.\n"
        )
        
        if needs_reasoning:
            system_prompt = base_system_prompt + (
                "\nThis task requires careful reasoning and analysis. "
                "Include detailed comments explaining your approach and why certain decisions were made. "
                "Be thorough in your implementation with proper error handling and edge case coverage."
            ) + parameter_handling_instructions
        else:
            system_prompt = base_system_prompt + (
                "\nGenerate concise code that directly addresses the task. "
                "Focus on clarity and efficiency in your implementation."
            ) + parameter_handling_instructions
    
    # Debug info
    logger.info(f"🔵 [{request_id}] Streaming Claude response for prompt: {prompt[:100]}...")
    logger.info(f"🔵 [{request_id}] Reasoning flag: {needs_reasoning}")
    logger.info(f"🔵 [{request_id}] Using system prompt: {system_prompt[:100]}...")
    logger.info(f"🔵 [{request_id}] Available tools: {[t['name'] for t in tools]}")
    
    # Helper function to handle tool usage with detailed debugging
    async def handle_tool_use(message_id, tool_name, tool_input):
        logger.info(f"🛠️ [{request_id}] Tool use: {tool_name} with input: {tool_input}")
        
        try:
            # Execute the tool with the provided input
            result = tool_registry.run_tool(tool_name, tool_input)
            logger.info(f"🛠️ [{request_id}] Tool result: {result[:100]}...")
            
            # Return the tool result for streaming and to Claude
            return {
                "id": message_id,
                "tool": tool_name,
                "result": result
            }
        except Exception as e:
            error_message = f"Tool execution error: {str(e)}"
            logger.error(f"❌ [{request_id}] {error_message}")
            logger.error(f"❌ [{request_id}] Traceback: {traceback.format_exc()}")
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
                        logger.debug(f"🛠️ [{request_id}] Tool use delta: {message.delta.tool_use}")
                
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
                    logger.info(f"🏁 [{request_id}] Claude message complete")
                    yield {"phase": "claude", "type": "done"}
    
    except Exception as e:
        logger.error(f"❌ [{request_id}] Error in Claude stream: {str(e)}")
        logger.error(f"❌ [{request_id}] Traceback: {traceback.format_exc()}")
        yield {"phase": "claude", "type": "error", "content": f"Error: {str(e)}"}
        yield {"phase": "claude", "type": "done"}

# Enhanced version with parameter identification
async def identify_parameters(
    prompt: str,
    tool_registry: ToolRegistry
) -> AsyncGenerator[dict, None]:
    """
    Special mode to have Claude identify required parameters before code generation
    """
    request_id = f"param-{int(asyncio.get_event_loop().time() * 1000)}"
    
    parameter_system_prompt = (
        "You are a requirements analyst identifying required parameters for a coding task. "
        "Your job is to identify ALL parameters needed to implement the user's request. "
        "For each parameter, provide a clear name, description, default value if applicable, "
        "and whether it's required. Focus ONLY on identifying parameters, not solving the task."
    )
    
    # Enhance the prompt to direct Claude to identify parameters
    parameter_prompt = f"""
    {prompt}
    
    INSTRUCTION: First, identify ALL information needed to implement this solution. 
    DO NOT generate code yet. Instead, create a JSON object listing all required parameters.
    
    For each parameter:
    1. Provide a parameter name (use snake_case)
    2. Explain why it's needed
    3. Suggest a default value if available (or null if no default is possible)
    4. Mark it as required=true or required=false
    
    Format your response as valid JSON like this:
    ```json
    {{
        "parameters": [
            {{
                "name": "document_id",
                "description": "Google Drive document ID to access",
                "default": null,
                "required": true
            }},
            {{
                "name": "email_recipient",
                "description": "Email address to send the summary to",
                "default": null,
                "required": true 
            }},
            {{
                "name": "summary_ratio",
                "description": "Percentage of original text to include in summary (0.0-1.0)",
                "default": 0.2,
                "required": false
            }}
        ]
    }}
    ```
    
    IMPORTANT: Think comprehensively to identify ALL needed parameters.
    """
    
    logger.info(f"🔍 [{request_id}] Identifying parameters for prompt: {prompt[:100]}...")
    
    try:
        yield {"phase": "reasoning", "type": "parameters_start", "content": "Identifying required parameters..."}
        
        # Use Claude to identify parameters
        response = await claude.messages.create(
            model="claude-3-7-sonnet-20250219",
            messages=[{"role": "user", "content": parameter_prompt}],
            system=parameter_system_prompt,
            temperature=0.2,
            max_tokens=2000
        )
        
        # Extract the JSON from the response
        response_content = response.content[0].text
        logger.info(f"🔍 [{request_id}] Parameter identification response: {response_content[:200]}...")
        
        # Try to parse JSON from the response
        try:
            # Extract JSON from markdown code block if present
            json_match = None
            if "```json" in response_content:
                json_blocks = response_content.split("```json")
                if len(json_blocks) > 1:
                    json_content = json_blocks[1].split("```")[0].strip()
                    json_match = json_content
            elif "```" in response_content:
                json_blocks = response_content.split("```")
                if len(json_blocks) > 1:
                    json_content = json_blocks[1].strip()
                    json_match = json_content
            else:
                # Try to find JSON object in the text
                import re
                json_match = re.search(r'\{[\s\S]*\}', response_content)
                if json_match:
                    json_match = json_match.group(0)
            
            if json_match:
                parameters = json.loads(json_match)
                logger.info(f"🔍 [{request_id}] Extracted parameters: {parameters}")
                
                # Return the parameters
                yield {
                    "phase": "reasoning", 
                    "type": "parameters", 
                    "content": parameters
                }
            else:
                logger.error(f"❌ [{request_id}] Failed to extract JSON from Claude's response")
                yield {
                    "phase": "reasoning", 
                    "type": "parameters_error", 
                    "content": "Failed to extract parameters from the response."
                }
        except json.JSONDecodeError as e:
            logger.error(f"❌ [{request_id}] JSON parsing error: {str(e)}")
            logger.error(f"❌ [{request_id}] Raw response: {response_content}")
            yield {
                "phase": "reasoning", 
                "type": "parameters_error", 
                "content": f"Failed to parse parameters JSON: {str(e)}"
            }
        
        yield {"phase": "reasoning", "type": "parameters_done", "content": "Parameter identification complete"}
        
    except Exception as e:
        logger.error(f"❌ [{request_id}] Error identifying parameters: {str(e)}")
        logger.error(f"❌ [{request_id}] Traceback: {traceback.format_exc()}")
        yield {
            "phase": "reasoning", 
            "type": "parameters_error", 
            "content": f"Error identifying parameters: {str(e)}"
        }
        yield {"phase": "reasoning", "type": "parameters_done", "content": "Parameter identification failed"}

# Function to generate code with parameters
async def generate_code_with_parameters(
    prompt: str,
    parameters: List[Dict[str, Any]],
    tool_registry: ToolRegistry,
    needs_reasoning: bool = False
) -> AsyncGenerator[dict, None]:
    """
    Generate code with specific parameters to avoid Claude asking questions
    """
    request_id = f"gen-{int(asyncio.get_event_loop().time() * 1000)}"
    
    # Enhance the prompt with the parameters
    parameter_info = "\n\nPARAMETER VALUES:\n"
    for param in parameters:
        name = param.get("name", "unknown")
        value = param.get("value", "null")
        parameter_info += f"- {name}: {value}\n"
    
    enhanced_prompt = f"""
    {prompt}
    
    {parameter_info}
    
    IMPORTANT: Use these provided parameter values in your implementation. Do not ask for additional information.
    Generate complete, working code that implements the requested functionality.
    """
    
    logger.info(f"🧩 [{request_id}] Generating code with parameters: {parameters}")
    
    # Stream the enhanced Claude response
    async for chunk in stream_enhanced_claude(
        prompt=enhanced_prompt,
        tool_registry=tool_registry,
        needs_reasoning=needs_reasoning,
        temperature=0.2
    ):
        yield chunk

# Alias for backward compatibility
stream_claude_tool_use = stream_enhanced_claude