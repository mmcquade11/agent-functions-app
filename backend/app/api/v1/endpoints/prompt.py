# app/api/v1/endpoints/prompt.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.schemas.prompt import OptimizePromptRequest, OptimizePromptResponse, RoutePromptRequest, RoutePromptResponse, PromptCreate, PromptResponse
from app.models.prompt import Prompt
from app.api.deps import get_current_user
from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError
from uuid import uuid4
from app.core.config import settings
import logging
import traceback
import time
import json
from typing import Dict, Any, List, Optional, Union

# Import optimized functions from the updated LLM wrappers
from app.services.llm_wrappers import optimize_regular_prompt, real_optimize_prompt

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# -- Route Prompt Function (Needs Reasoning or Not) -- 
async def determine_reasoning_need(prompt: str) -> bool:
    """
    Determine if a prompt requires reasoning based on its complexity.
    Returns True if reasoning is needed, False otherwise.
    """
    request_id = str(uuid4())
    logger.info(f"[RequestID: {request_id}] Evaluating if prompt needs reasoning: {prompt[:100]}...")
    
    try:
        client = AsyncOpenAI(
            base_url=settings.OPENAI_BASE_URL if hasattr(settings, 'OPENAI_BASE_URL') else None,
            api_key=settings.OPENAI_API_KEY,
        )

        system_prompt = """
        You are tasked with classifying if a request requires step-by-step reasoning or can be solved directly.

        Evaluate if the request has these characteristics that would require reasoning:
        1. Involves multiple distinct steps or phases
        2. Requires coordination between different systems or tools
        3. Has complex business logic or conditional flows
        4. Needs careful error handling across multiple operations
        5. Involves sequential dependencies where later steps rely on earlier ones

        Examples that need reasoning:
        - Creating a workflow that monitors changes in one system and updates another
        - Building multi-stage data processing pipelines
        - Implementing complex business logic with many conditions
        
        Examples that DON'T need reasoning:
        - Simple data retrieval from a single source
        - Basic communication with a single API
        - Straightforward formatting or parsing tasks
        
        Respond ONLY with "true" if reasoning is needed or "false" if it's not. No explanation.
        """

        start_time = time.time()
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system", 
                    "content": system_prompt
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            timeout=30,  # Add timeout
        )
        elapsed_time = time.time() - start_time
        logger.info(f"[RequestID: {request_id}] OpenAI API call took {elapsed_time:.2f} seconds")

        reasoning_flag = response.choices[0].message.content.strip().lower()
        logger.info(f"[RequestID: {request_id}] Reasoning determination result: {reasoning_flag}")

        return "true" in reasoning_flag
    except APIError as e:
        logger.error(f"[RequestID: {request_id}] OpenAI API Error in determine_reasoning_need: {str(e)}", exc_info=True)
        # Default to false on API error
        return False
    except Exception as e:
        logger.error(f"[RequestID: {request_id}] Error determining reasoning need: {str(e)}", exc_info=True)
        logger.error(f"[RequestID: {request_id}] Traceback: {traceback.format_exc()}")
        # Default to false on general error
        return False

# -- Parameter Detection Function -- 
async def detect_missing_parameters(prompt: str) -> List[Dict[str, Any]]:
    """
    Use GPT-4o to detect if there are missing parameters in the prompt that Claude might ask about.
    Returns a list of parameter objects.
    """
    request_id = str(uuid4())
    logger.info(f"[RequestID: {request_id}] Detecting missing parameters: {prompt[:100]}...")
    
    try:
        client = AsyncOpenAI(
            base_url=settings.OPENAI_BASE_URL if hasattr(settings, 'OPENAI_BASE_URL') else None,
            api_key=settings.OPENAI_API_KEY,
        )

        system_prompt = """
        You are a parameter analyzer helping to prepare prompts for a code-generating AI.
        Your job is to identify any critical parameters that are missing from the user's prompt.
        
        For each missing parameter:
        1. Provide a parameter name (use snake_case)
        2. Explain why it's needed
        3. Suggest a default value if available (or null if no default is possible)
        4. Mark it as required=true or required=false
        
        Format your response as valid JSON.
        """

        parameter_prompt = f"""
        Based on this prompt:
        
        "{prompt}"
        
        Identify any missing parameters that would be needed to implement this request.
        Focus on:
        - API authentication details
        - File/document identifiers
        - Email addresses
        - Connection details
        - Configuration values
        
        Format your response ONLY as valid JSON like this:
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
                }}
            ]
        }}
        ```
        
        If no parameters are missing or needed, return an empty parameters array.
        """

        start_time = time.time()
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system", 
                    "content": system_prompt
                },
                {"role": "user", "content": parameter_prompt}
            ],
            temperature=0.2,
            timeout=30,
        )
        elapsed_time = time.time() - start_time
        logger.info(f"[RequestID: {request_id}] OpenAI API call took {elapsed_time:.2f} seconds")

        response_content = response.choices[0].message.content.strip()
        
        # Extract JSON from the response
        try:
            # Check for code block format
            if "```json" in response_content:
                json_content = response_content.split("```json")[1].split("```")[0].strip()
            elif "```" in response_content:
                json_content = response_content.split("```")[1].strip()
            else:
                # Try to extract just the JSON object
                import re
                match = re.search(r'\{[\s\S]*\}', response_content)
                json_content = match.group(0) if match else response_content
                
            # Parse the JSON
            parameters_data = json.loads(json_content)
            logger.info(f"[RequestID: {request_id}] Detected parameters: {parameters_data}")
            
            # Return the parameters list
            return parameters_data.get("parameters", [])
        except Exception as e:
            logger.error(f"[RequestID: {request_id}] Error parsing parameters JSON: {str(e)}", exc_info=True)
            logger.error(f"[RequestID: {request_id}] Raw content: {response_content}")
            return []
            
    except Exception as e:
        logger.error(f"[RequestID: {request_id}] Error detecting parameters: {str(e)}", exc_info=True)
        return []

# -- Helper Function for Safe Parameter Type Handling --
def sanitize_parameters(parameters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ensure all parameter fields have the correct types.
    This prevents Pydantic validation errors.
    """
    sanitized_params = []
    
    for param in parameters:
        # Create a clean copy of the parameter
        sanitized_param = {
            "name": str(param.get("name", "unknown")),
            "description": str(param.get("description", "")),
            "required": bool(param.get("required", True))
        }
        
        # Handle default value - convert to string if it's a number
        default_value = param.get("default")
        if default_value is not None:
            if isinstance(default_value, (int, float)):
                sanitized_param["default"] = str(default_value)
            else:
                sanitized_param["default"] = default_value
        else:
            sanitized_param["default"] = None
            
        sanitized_params.append(sanitized_param)
        
    return sanitized_params

# -- Optimize Prompt API Endpoint with Parameter Detection --
@router.post("/optimize-prompt", response_model=OptimizePromptResponse, status_code=status.HTTP_200_OK)
async def optimize_prompt(
    request: OptimizePromptRequest,
    current_user=Depends(get_current_user)
) -> OptimizePromptResponse:
    """
    Optimize a raw user prompt for clarity, task-focus, and completeness.
    Works in two modes:
    1. Conversation mode - Generates contextual follow-up questions
    2. Final mode - Creates structured prompt for Claude tool-use
    
    Now with parameter detection to help prevent Claude from asking questions.
    """
    request_id = str(uuid4())
    logger.info(f"[RequestID: {request_id}] Optimize prompt API called with: {request.prompt[:100]}...")
    
    if not request.prompt or not request.prompt.strip():
        logger.error(f"[RequestID: {request_id}] Empty prompt received")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt cannot be empty."
        )

    original_prompt = request.prompt
    optimized_prompt = ""
    detected_parameters = []

    try:
        # Detect which mode to use based on conversation markers
        is_conversation = "Assistant:" in request.prompt
        is_final_submission = request.prompt.count("You:") > 1 or len(request.prompt.split()) > 100
        
        # Extract the useful content from the prompt
        full_prompt = request.prompt
        extracted_prompt = request.prompt
        
        logger.info(f"[RequestID: {request_id}] Conversation: {is_conversation}, Final: {is_final_submission}")
        
        # If it's a conversation format, extract the latest content
        if "You:" in full_prompt:
            try:
                lines = full_prompt.split('\n')
                conversation_data = []
                
                # Parse conversation history
                for line in lines:
                    if line.startswith("You:") or line.startswith("Assistant:"):
                        conversation_data.append(line)
                
                # Check if this is a multi-turn conversation
                is_multi_turn = len([l for l in conversation_data if l.startswith("You:")]) > 1
                logger.info(f"[RequestID: {request_id}] Multi-turn conversation: {is_multi_turn}")
                
                # For the final submission, use the entire conversation
                if is_final_submission:
                    extracted_prompt = full_prompt
                # For early conversation turns, just use the latest
                elif not is_multi_turn:
                    for i in range(len(lines) - 1, -1, -1):
                        if lines[i].startswith("You:"):
                            extracted_prompt = lines[i][4:].strip()
                            break
            except Exception as e:
                logger.error(f"[RequestID: {request_id}] Error parsing conversation: {str(e)}", exc_info=True)
                # Continue with the original prompt
        
        # If this is a final submission, detect missing parameters
        if is_final_submission:
            logger.info(f"[RequestID: {request_id}] Detecting parameters for final submission")
            detected_parameters = await detect_missing_parameters(extracted_prompt)
            # Sanitize parameters to prevent type errors
            detected_parameters = sanitize_parameters(detected_parameters)
        
        # Choose optimization strategy with proper error handling
        start_time = time.time()
        
        if is_conversation and not is_final_submission:
            # Conversational mode - generate follow-up questions
            logger.info(f"[RequestID: {request_id}] Using conversational optimization for chat")
            try:
                optimized = await optimize_regular_prompt(full_prompt)
            except Exception as e:
                logger.error(f"[RequestID: {request_id}] Failed in optimize_regular_prompt: {str(e)}", exc_info=True)
                # Detect keywords for more contextual fallback
                prompt_lower = full_prompt.lower()
                
                # Highly specific fallback based on Google Drive and email detection
                if "google drive" in prompt_lower and "email" in prompt_lower:
                    optimized = "Thank you for providing those details about the Google Drive document and email address. Is there any specific format you'd like for the summary or any authentication details I should be aware of for accessing Google Drive?"
                elif "google drive" in prompt_lower:
                    optimized = "I understand you want to work with Google Drive documents. Could you tell me more about how you'd like to authenticate and what specific operations you want to perform with the documents?"
                elif "email" in prompt_lower:
                    optimized = "I see you mentioned sending emails. Could you provide details about any formatting requirements for these emails or any authentication methods you prefer?"
                else:
                    # Generic fallback
                    optimized = "Thank you for those details. To help create your agent, could you specify any authentication requirements or output formatting preferences you have?"
        else:
            # Final submission mode - create structured Claude prompt with parameter enhancements
            logger.info(f"[RequestID: {request_id}] Using final optimization for Claude tool-use")
            try:
                # First get the basic optimized prompt
                optimized = await real_optimize_prompt(extracted_prompt)
                
                # Enhance it with parameter instructions if we detected parameters
                if detected_parameters:
                    logger.info(f"[RequestID: {request_id}] Enhancing prompt with parameter instructions")
                    
                    # Add parameter guidance section
                    parameter_instructions = "\n\nPARAMETER GUIDANCE:\n"
                    parameter_instructions += "The following parameters should be used in your implementation:\n"
                    
                    for param in detected_parameters:
                        param_name = param.get("name", "unknown")
                        description = param.get("description", "")
                        default = param.get("default")
                        required = param.get("required", True)
                        
                        # Format the parameter guidance
                        if default is not None:
                            parameter_instructions += f"- {param_name}: {description} (Default: {default})\n"
                        else:
                            parameter_instructions += f"- {param_name}: {description} (No default, use placeholder)\n"
                    
                    # Add instruction to use default parameters
                    parameter_instructions += "\nIMPORTANT: Rather than asking for missing values, use the defaults or placeholder values indicated above."
                    
                    # Append to the optimized prompt
                    optimized += parameter_instructions
                
                # Always add Claude instructions to avoid asking questions
                optimized += """

IMPORTANT IMPLEMENTATION INSTRUCTIONS:
1. Generate complete, working code implementing this solution
2. Use default values for any missing information rather than asking questions
3. For Google Drive access, use a service account approach with credentials file
4. For document IDs, use placeholder IDs that the user can replace
5. For email credentials, use placeholder SMTP settings the user can replace
6. Always include detailed comments explaining what needs to be configured
7. Provide complete, runnable code - do not wait for more information

Example defaults to use:
- Google Drive document ID: Use "DOCUMENT_ID_HERE" as placeholder
- Authentication: Default to a service account approach with "service_account.json"
- Email: Use SMTP with placeholder credentials for Gmail
- Summarization: Default to extractive summarization at 20% length
"""
                
            except Exception as e:
                logger.error(f"[RequestID: {request_id}] Failed in real_optimize_prompt: {str(e)}", exc_info=True)
                
                # Create a structured fallback response
                prompt_lower = extracted_prompt.lower()
                contains_google_drive = "google drive" in prompt_lower or "drive" in prompt_lower
                contains_email = "email" in prompt_lower or "mail" in prompt_lower
                
                optimized = """
1. TASK OVERVIEW
Create a tool-using agent based on the user's requirements.

2. REQUIRED CAPABILITIES
"""
                if contains_google_drive:
                    optimized += "- Google Drive API for document access and manipulation\n"
                if contains_email:
                    optimized += "- Email functionality via a suitable library\n"
                
                optimized += """
3. IMPLEMENTATION REQUIREMENTS
- Use secure authentication methods
- Include proper error handling
- Implement logging for debugging

4. OUTPUT REQUIREMENTS
- Provide clear success/failure messages
- Format results according to user preferences

5. TOOL-USE FORMAT
Implement this using Claude's tool-use capabilities to create a functional agent with the necessary components.

IMPORTANT: Generate complete code using default or placeholder values rather than asking for additional information.
"""
        
        elapsed_time = time.time() - start_time
        optimized_prompt = optimized
        logger.info(f"[RequestID: {request_id}] Optimization complete in {elapsed_time:.2f}s: {optimized[:100]}...")
        
    except Exception as e:
        logger.error(f"[RequestID: {request_id}] Failed to optimize prompt: {str(e)}", exc_info=True)
        logger.error(f"[RequestID: {request_id}] Traceback: {traceback.format_exc()}")
        
        # Create a generic fallback response that will still work
        prompt_lower = request.prompt.lower()
        contains_google_drive = "google drive" in prompt_lower or "drive" in prompt_lower or "doc" in prompt_lower
        contains_email = "email" in prompt_lower or "mail" in prompt_lower
        
        fallback_response = ""
        
        if contains_google_drive and contains_email:
            fallback_response = """
1. TASK OVERVIEW
Create an agent that retrieves a document from Google Drive, generates a summary, and sends it via email.

2. REQUIRED CAPABILITIES
- Google Drive API access
- Text summarization functionality
- Email sending capability

3. IMPLEMENTATION REQUIREMENTS
- Authenticate securely with Google Drive
- Process document content for summarization
- Send formatted email with the summary

4. OUTPUT REQUIREMENTS
- Log successful operations
- Provide error messages for any failures

5. TOOL-USE FORMAT
Implement this using Claude's tool-use capabilities to create a functional, error-resilient agent.

IMPORTANT: Generate complete code using default or placeholder values rather than asking for additional information.
"""
        else:
            fallback_response = """
1. TASK OVERVIEW
Create an agent that automates the workflow based on the user's requirements.

2. REQUIRED CAPABILITIES
- API access to required services
- Data processing functionality
- Output generation capability

3. IMPLEMENTATION REQUIREMENTS
- Implement secure authentication
- Include error handling and logging
- Create maintainable, modular code

4. OUTPUT REQUIREMENTS
- Return results in the desired format
- Provide clear status updates

5. TOOL-USE FORMAT
Implement this using Claude's tool-use capabilities to create a functional agent with the necessary components.

IMPORTANT: Generate complete code using default or placeholder values rather than asking for additional information.
"""
        
        optimized_prompt = fallback_response
        # Empty the parameters if there was an error
        detected_parameters = []

    # Always return a valid OptimizePromptResponse
    # Use an empty parameters list if detection failed to prevent Pydantic validation errors
    sanitized_parameters = detected_parameters if detected_parameters else []
    
    try:
        # Double check that parameters won't cause validation errors
        return OptimizePromptResponse(
            original_prompt=original_prompt,
            optimized_prompt=optimized_prompt,
            parameters=sanitized_parameters
        )
    except Exception as e:
        # Fall back to a completely safe response with empty parameters
        logger.error(f"[RequestID: {request_id}] Error creating response object: {str(e)}", exc_info=True)
        return OptimizePromptResponse(
            original_prompt=original_prompt,
            optimized_prompt=optimized_prompt,
            parameters=[]
        )

# -- Route Prompt API Endpoint --
@router.post("/route-prompt", response_model=RoutePromptResponse, status_code=status.HTTP_200_OK)
async def route_prompt(
    request: RoutePromptRequest,
    current_user=Depends(get_current_user)
) -> RoutePromptResponse:
    """
    Classify a prompt as needing Reasoning vs Task-only using GPT-4o.
    """
    request_id = str(uuid4())
    logger.info(f"[RequestID: {request_id}] Route prompt API called with: {request.prompt[:100]}...")

    if not request.prompt or not request.prompt.strip():
        logger.error(f"[RequestID: {request_id}] Empty prompt received")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt cannot be empty."
        )

    try:
        needs_reasoning = await determine_reasoning_need(request.prompt)
        logger.info(f"[RequestID: {request_id}] Routing result - needs_reasoning: {needs_reasoning}")
    except Exception as e:
        logger.error(f"[RequestID: {request_id}] Failed to route prompt: {str(e)}", exc_info=True)
        logger.error(f"[RequestID: {request_id}] Traceback: {traceback.format_exc()}")
        
        # Default to False on error - simpler path
        needs_reasoning = False
        logger.info(f"[RequestID: {request_id}] Defaulting to needs_reasoning=False due to error")

    return RoutePromptResponse(
        prompt=request.prompt,
        needs_reasoning=needs_reasoning
    )

@router.post("/", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
async def save_prompt(
    payload: PromptCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Save a prompt to the database after optimization.
    """
    request_id = str(uuid4())
    logger.info(f"[RequestID: {request_id}] Saving prompt: {payload.original_prompt[:50]}...")
    
    try:
        prompt_id = uuid4()
        prompt = Prompt(
            id=prompt_id,
            user_id=current_user.sub,
            original_prompt=payload.original_prompt,
            optimized_prompt=payload.optimized_prompt,
            needs_reasoning=str(payload.needs_reasoning).lower()
        )
        db.add(prompt)
        await db.commit()
        await db.refresh(prompt)
        logger.info(f"[RequestID: {request_id}] Prompt saved with ID: {prompt.id}")
        return prompt
    except Exception as e:
        logger.error(f"[RequestID: {request_id}] Error saving prompt: {str(e)}", exc_info=True)
        # Rollback on error
        try:
            await db.rollback()
        except Exception as rollback_err:
            logger.error(f"[RequestID: {request_id}] Error in rollback: {str(rollback_err)}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save prompt: {str(e)}"
        )