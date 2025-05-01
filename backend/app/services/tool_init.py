# app/services/tool_init.py

from app.services.tool_registry import ToolRegistry

# Create and initialize the registry
registry = ToolRegistry()

# Register tools
registry.register_tool(
    name="example_tool",
    description="An example tool",
    input_schema={
        "type": "object",
        "properties": {
            "input": {"type": "string"}
        },
        "required": ["input"]
    },
    func=lambda input_data: f"Processed: {input_data['input']}"
)

# Add more tools as needed