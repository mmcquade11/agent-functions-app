# app/services/custom_integrations.py

import requests
import json
import os
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class CustomIntegration:
    """Base class for custom integrations that aren't directly supported by Claude"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return the tool definition in Claude's tool format"""
        raise NotImplementedError("Subclasses must implement get_tool_definition")
    
    def execute(self, inputs: Dict[str, Any]) -> str:
        """Execute the integration with the given inputs"""
        raise NotImplementedError("Subclasses must implement execute")


class SlackIntegration(CustomIntegration):
    """Integration with Slack API"""
    
    def __init__(self, api_token: str):
        super().__init__(
            name="slack_message_sender",
            description="Send messages to Slack channels or users"
        )
        self.api_token = api_token
    
    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "Channel ID or user ID to send message to"
                    },
                    "message": {
                        "type": "string",
                        "description": "Message text to send"
                    },
                    "blocks": {
                        "type": "string",
                        "description": "Optional: JSON string of Slack blocks"
                    }
                },
                "required": ["channel", "message"]
            }
        }
    
    def execute(self, inputs: Dict[str, Any]) -> str:
        channel = inputs.get("channel")
        message = inputs.get("message")
        blocks = inputs.get("blocks")
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "channel": channel,
            "text": message
        }
        
        if blocks:
            try:
                payload["blocks"] = json.loads(blocks)
            except json.JSONDecodeError:
                return "Error: 'blocks' must be a valid JSON string"
        
        try:
            response = requests.post(
                "https://slack.com/api/chat.postMessage",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    return f"Message sent successfully to {channel}"
                else:
                    return f"Error: {data.get('error', 'Unknown error')}"
            else:
                return f"Error: HTTP {response.status_code}"
                
        except Exception as e:
            logger.error(f"Error in Slack integration: {str(e)}")
            return f"Error: {str(e)}"


class GoogleCalendarIntegration(CustomIntegration):
    """Integration with Google Calendar API (simplified example)"""
    
    def __init__(self, credentials_file: str):
        super().__init__(
            name="google_calendar_event_creator",
            description="Create events in Google Calendar"
        )
        self.credentials_file = credentials_file
        # In a real implementation, you would initialize the Google Calendar API client here
    
    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Event title/summary"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time in ISO format (YYYY-MM-DDTHH:MM:SS)"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in ISO format (YYYY-MM-DDTHH:MM:SS)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Event description"
                    },
                    "attendees": {
                        "type": "string",
                        "description": "Comma-separated list of email addresses"
                    }
                },
                "required": ["summary", "start_time", "end_time"]
            }
        }
    
    def execute(self, inputs: Dict[str, Any]) -> str:
        # This is a simplified example
        # In a real implementation, you would use the Google Calendar API client
        try:
            return f"Created event '{inputs['summary']}' from {inputs['start_time']} to {inputs['end_time']}"
        except Exception as e:
            logger.error(f"Error in Google Calendar integration: {str(e)}")
            return f"Error: {str(e)}"


class HuggingFaceModelIntegration(CustomIntegration):
    """Integration with Hugging Face models"""
    
    def __init__(self, api_token: str, model_id: str):
        super().__init__(
            name=f"huggingface_{model_id.replace('/', '_')}",
            description=f"Run inference on the HuggingFace model {model_id}"
        )
        self.api_token = api_token
        self.model_id = model_id
    
    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "inputs": {
                        "type": "string",
                        "description": "Input text to send to the model"
                    },
                    "parameters": {
                        "type": "string",
                        "description": "Optional: JSON string of inference parameters"
                    }
                },
                "required": ["inputs"]
            }
        }
    
    def execute(self, inputs: Dict[str, Any]) -> str:
        model_inputs = inputs.get("inputs")
        parameters_str = inputs.get("parameters", "{}")
        
        try:
            parameters = json.loads(parameters_str) if parameters_str else {}
        except json.JSONDecodeError:
            return "Error: 'parameters' must be a valid JSON string"
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "inputs": model_inputs,
            **parameters
        }
        
        try:
            api_url = f"https://api-inference.huggingface.co/models/{self.model_id}"
            response = requests.post(api_url, headers=headers, json=payload)
            
            if response.status_code == 200:
                return response.text
            else:
                return f"Error: HTTP {response.status_code} - {response.text}"
                
        except Exception as e:
            logger.error(f"Error in HuggingFace integration: {str(e)}")
            return f"Error: {str(e)}"


# Integration registry to manage all custom integrations
class IntegrationRegistry:
    def __init__(self):
        self.integrations: Dict[str, CustomIntegration] = {}
    
    def register_integration(self, integration: CustomIntegration):
        """Register a custom integration"""
        self.integrations[integration.name] = integration
        logger.info(f"Registered custom integration: {integration.name}")
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get all tool definitions for Claude"""
        return [
            integration.get_tool_definition() 
            for integration in self.integrations.values()
        ]
    
    def execute_integration(self, name: str, inputs: Dict[str, Any]) -> str:
        """Execute a custom integration"""
        if name not in self.integrations:
            return f"Error: Integration '{name}' not found"
        
        try:
            return self.integrations[name].execute(inputs)
        except Exception as e:
            logger.error(f"Error executing integration {name}: {str(e)}")
            return f"Error executing {name}: {str(e)}"