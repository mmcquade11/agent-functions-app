# app/services/tool_registry.py

from typing import Callable, Dict, List, Any, Optional

class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register_tool(
        self, 
        name: str, 
        description: str, 
        input_schema: dict,
        func: Callable[[dict], str],
        required_fields: Optional[List[str]] = None
    ):
        """
        Register a tool with the registry.
        
        Args:
            name: Tool name (must be a valid identifier)
            description: Detailed description of what the tool does
            input_schema: JSON Schema for the tool's input
            func: Function to execute when the tool is called
            required_fields: List of required fields in the input schema
        """
        # If required fields are provided, add them to the schema
        if required_fields:
            input_schema["required"] = required_fields
        
        # Ensure schema has type: object
        if "type" not in input_schema:
            input_schema["type"] = "object"
            
        self.tools[name] = {
            "name": name,
            "description": description,
            "input_schema": input_schema,
            "function": func,
        }
        
        print(f"🔧 Registered tool: {name}")

    def get_tools_for_claude(self) -> List[dict]:
        """
        Get tools in the format required by Claude's Integrations API.
        """
        claude_tools = []
        for tool in self.tools.values():
            claude_tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["input_schema"],
            })
        
        print(f"🔧 Provided {len(claude_tools)} tools to Claude")
        return claude_tools

    def run_tool(self, tool_name: str, tool_input: dict) -> str:
        """
        Execute a tool with the given input.
        
        Args:
            tool_name: Name of the tool to execute
            tool_input: Input data for the tool
            
        Returns:
            The result of the tool execution as a string
        """
        tool = self.tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool {tool_name} not registered")
        
        try:
            result = tool["function"](tool_input)
            return result
        except Exception as e:
            raise RuntimeError(f"Error executing tool {tool_name}: {str(e)}")

    def list_tools(self) -> List[str]:
        """List all registered tool names"""
        return list(self.tools.keys())