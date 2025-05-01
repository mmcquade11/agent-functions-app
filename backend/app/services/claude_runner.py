# app/services/claude_runner.py

import asyncio
from anthropic import AsyncAnthropic, HUMAN_PROMPT, AI_PROMPT
from app.services.tool_registry import ToolRegistry  # Correct import path
from typing import AsyncGenerator
from app.core.config import settings 

# Load API key from environment variables via settings
claude = AsyncAnthropic(api_key=settings.CLAUDE_API_KEY)

async def stream_claude_tool_use(prompt: str, tool_registry: ToolRegistry) -> AsyncGenerator[dict, None]:
    tools = tool_registry.get_tools_for_claude()

    async with claude.messages.stream(
        model="claude-3-7-sonnet-20250219",
        messages=[{"role": "user", "content": prompt}],
        tools=tools,
        max_tokens=1024,
    ) as stream:
        async for message in stream:
            if message.type == "message_start":
                yield { "phase": "claude", "type": "start" }
            elif message.type == "content_block_delta":
                # Fix: TextDelta object handling
                if hasattr(message.delta, "text"):
                    yield { "phase": "claude", "type": "text", "content": message.delta.text }
                else:
                    # Handle other delta types if needed
                    pass
            elif message.type == "tool_use":
                tool_name = message.name
                tool_input = message.input
                yield { "phase": "claude", "type": "tool_use", "tool": tool_name, "input": tool_input }

                # Run tool
                try:
                    result = tool_registry.run_tool(tool_name, tool_input)
                except Exception as e:
                    result = f"Tool execution error: {str(e)}"

                yield { "phase": "claude", "type": "tool_result", "tool": tool_name, "result": result }

                await stream.send_tool_result(tool_use_id=message.id, content=result)

            elif message.type == "message_stop":
                yield { "phase": "claude", "type": "done" }