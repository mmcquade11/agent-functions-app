# app/services/tool_init.py

import json
import requests
import os
from datetime import datetime
import logging
from app.services.tool_registry import ToolRegistry
from app.services.custom_integrations import (
    IntegrationRegistry,
    SlackIntegration,
    GoogleCalendarIntegration,
    HuggingFaceModelIntegration
)
from app.core.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create global registry instances
tool_registry = ToolRegistry()
integration_registry = IntegrationRegistry()

# Initialize built-in tools
# ------------------------

# Helper function to run Python code safely
def execute_python_code(inputs):
    code = inputs.get("code", "")
    
    # Safety check - replace with your own safety checks
    if "import os" in code or "import subprocess" in code:
        return "Error: Potentially unsafe code detected"
    
    try:
        # Execute code in a restricted environment
        local_vars = {}
        exec(code, {"__builtins__": {"print": print}}, local_vars)
        
        # Capture any returned value
        result = local_vars.get("result", "Code executed successfully but no result variable was set")
        return str(result)
    except Exception as e:
        return f"Error executing code: {str(e)}"

# Register a Python code execution tool
tool_registry.register_tool(
    name="python_code_executor",
    description="Executes Python code and returns the result. The code should set a 'result' variable with the return value.",
    input_schema={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute"
            }
        }
    },
    func=execute_python_code,
    required_fields=["code"]
)

# Register a web search tool
def web_search(inputs):
    query = inputs.get("query", "")
    
    # Mock implementation - replace with actual search API
    return json.dumps({
        "results": [
            {"title": "Example result 1 for: " + query, "url": "https://example.com/1"},
            {"title": "Example result 2 for: " + query, "url": "https://example.com/2"},
        ]
    })

tool_registry.register_tool(
    name="web_search",
    description="Search the web for information. Returns search results as JSON.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            }
        }
    },
    func=web_search,
    required_fields=["query"]
)

# Initialize custom integrations
# ----------------------------

# Only register if API keys/credentials are available
if hasattr(settings, "SLACK_API_TOKEN") and settings.SLACK_API_TOKEN:
    # Register Slack integration
    slack_integration = SlackIntegration(api_token=settings.SLACK_API_TOKEN)
    integration_registry.register_integration(slack_integration)
    
    # Create an adapter function that bridges the integration to our tool registry
    def slack_tool_adapter(inputs):
        return integration_registry.execute_integration("slack_message_sender", inputs)
    
    # Register the adapter as a tool
    tool_definition = slack_integration.get_tool_definition()
    tool_registry.register_tool(
        name=tool_definition["name"],
        description=tool_definition["description"],
        input_schema=tool_definition["input_schema"],
        func=slack_tool_adapter
    )

if hasattr(settings, "GOOGLE_CREDENTIALS_FILE") and settings.GOOGLE_CREDENTIALS_FILE:
    # Register Google Calendar integration
    calendar_integration = GoogleCalendarIntegration(
        credentials_file=settings.GOOGLE_CREDENTIALS_FILE
    )
    integration_registry.register_integration(calendar_integration)
    
    # Create adapter function
    def calendar_tool_adapter(inputs):
        return integration_registry.execute_integration(
            "google_calendar_event_creator", 
            inputs
        )
    
    # Register adapter as tool
    tool_definition = calendar_integration.get_tool_definition()
    tool_registry.register_tool(
        name=tool_definition["name"],
        description=tool_definition["description"],
        input_schema=tool_definition["input_schema"],
        func=calendar_tool_adapter
    )

if hasattr(settings, "HUGGINGFACE_API_TOKEN") and settings.HUGGINGFACE_API_TOKEN:
    # You can register multiple HuggingFace models
    hf_models = [
        "facebook/bart-large-cnn",  # Summarization model
        "deepset/roberta-base-squad2"  # Question answering model
    ]
    
    for model_id in hf_models:
        # Create integration
        hf_integration = HuggingFaceModelIntegration(
            api_token=settings.HUGGINGFACE_API_TOKEN,
            model_id=model_id
        )
        integration_registry.register_integration(hf_integration)
        
        # Create adapter
        def create_hf_adapter(name):
            def hf_adapter(inputs):
                return integration_registry.execute_integration(name, inputs)
            return hf_adapter
        
        # Register adapter
        tool_definition = hf_integration.get_tool_definition()
        tool_registry.register_tool(
            name=tool_definition["name"],
            description=tool_definition["description"],
            input_schema=tool_definition["input_schema"],
            func=create_hf_adapter(hf_integration.name)
        )

# Make the registry available to other modules
registry = tool_registry

# Print registered tools for debugging
logger.info(f"Initialized tool registry with {len(registry.list_tools())} tools:")
for tool_name in registry.list_tools():
    logger.info(f"- {tool_name}")