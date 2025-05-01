# agents/tool_registry.py

from typing import Callable, Dict, List, Any

class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register_tool(self, name: str, description: str, input_schema: dict, func: Callable[[dict], str]):
        self.tools[name] = {
            "name": name,
            "description": description,
            "input_schema": input_schema,
            "function": func,
        }

    def get_tools_for_claude(self) -> List[dict]:
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["input_schema"],
            }
            for tool in self.tools.values()
        ]

    def run_tool(self, tool_name: str, tool_input: dict) -> str:
        tool = self.tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool {tool_name} not registered")
        return tool["function"](tool_input)
