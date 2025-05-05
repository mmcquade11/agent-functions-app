# app/services/llm_wrappers.py
import logging
import json
import traceback
from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError
from app.core.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the OpenAI client properly
client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    # Add base_url if you're using a custom endpoint
    base_url=settings.OPENAI_BASE_URL if hasattr(settings, 'OPENAI_BASE_URL') else None
)

# GPT-4o call to optimize prompt
async def call_gpt_4o(system_prompt: str, user_prompt: str) -> str:
    """General purpose function to call GPT-4o with any system and user prompt"""
    logger.info(f"Calling GPT-4o with prompt: {user_prompt[:50]}...")
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
        )
        result = response.choices[0].message.content.strip()
        logger.info(f"GPT-4o response: {result[:100]}...")
        return result
    except APIError as e:
        logger.error(f"OpenAI API Error in call_gpt_4o: {str(e)}", exc_info=True)
        logger.error(f"Request parameters: system_prompt={system_prompt[:50]}..., user_prompt={user_prompt[:50]}...")
        return f"I encountered an API error while processing your request. {str(e)}"
    except RateLimitError as e:
        logger.error(f"OpenAI Rate Limit Error: {str(e)}")
        return "I'm currently experiencing high demand. Please try again in a moment."
    except APIConnectionError as e:
        logger.error(f"OpenAI API Connection Error: {str(e)}")
        return "I'm having trouble connecting to my services. Please check your internet connection and try again."
    except Exception as e:
        logger.error(f"Unexpected error in call_gpt_4o: {str(e)}", exc_info=True)
        logger.error(f"Traceback: {traceback.format_exc()}")
        return "I experienced an unexpected error. Let's try a different approach to your request."

# OpenAI o3 reasoning agent chain
async def call_openai_o3_reasoning(prompt: str) -> str:
    """
    Process a prompt through a reasoning agent to help users develop tool-using agents
    through a conversational approach that helps break down complex tasks.
    """
    logger.info(f"Calling reasoning agent with prompt: {prompt[:50]}...")
    
    # Check if this is follow-up in a conversation
    is_follow_up = False
    if "You:" in prompt and "Assistant:" in prompt:
        is_follow_up = True
        logger.info("Detected follow-up conversation")
    
    # Create an appropriate system prompt
    system_prompt = (
        "You are a senior AI assistant helping users develop tool-using agents. "
        "Your goal is to efficiently gather requirements through minimal conversation. "
        "When users explain what they want, acknowledge their needs and build upon them, "
        "adding your knowledge of best practices. "
        
        "If the user mentions specific tools or data sources (like Google Drive, Slack, etc.), "
        "ask targeted questions about those specific services. "
        
        "Avoid asking questions about services they did not mention. "
        "If more information is needed, ask 1-2 specific questions focusing on: "
        "1. What data sources they need to access "
        "2. What operations they want to perform "
        "3. Where results should be delivered "
        
        "Respond naturally and conversationally. Vary your responses and avoid templates. "
        "Make each response helpful and tailored to their specific request."
    )
    
    # Prepare messages for API call
    messages = [{"role": "system", "content": system_prompt}]
    
    # For follow-up conversations, use the history to provide context
    if is_follow_up:
        try:
            # Extract the conversation history
            lines = prompt.split('\n')
            current_role = None
            current_content = []
            conversation = []
            
            for line in lines:
                if line.startswith("You:"):
                    if current_role:
                        conversation.append({"role": current_role, "content": "\n".join(current_content)})
                    current_role = "user"
                    current_content = [line[4:].strip()]
                elif line.startswith("Assistant:"):
                    if current_role:
                        conversation.append({"role": current_role, "content": "\n".join(current_content)})
                    current_role = "assistant"
                    current_content = [line[10:].strip()]
                elif line.strip() and current_role:
                    current_content.append(line.strip())
            
            if current_role:
                conversation.append({"role": current_role, "content": "\n".join(current_content)})
            
            # Add the conversation history to messages
            for msg in conversation:
                messages.append({"role": "user" if msg["role"] == "user" else "assistant", "content": msg["content"]})
            
            logger.info(f"Extracted {len(conversation)} messages from conversation history")
        except Exception as e:
            logger.error(f"Error parsing conversation history: {str(e)}", exc_info=True)
            # Fallback to simpler approach
            messages.append({"role": "user", "content": prompt})
    else:
        # If not a follow-up, just use the prompt directly
        messages.append({"role": "user", "content": prompt})
    
    try:
        # Call OpenAI with the constructed messages
        response = await client.chat.completions.create(
            model="gpt-4o",  # Use gpt-4o by default
            messages=messages,
            temperature=0.7,  # Slightly higher temperature for more varied responses
        )
        
        result = response.choices[0].message.content.strip()
        logger.info(f"Reasoning agent response: {result[:100]}...")
        return result
    except APIError as e:
        logger.error(f"OpenAI API Error in reasoning agent: {str(e)}", exc_info=True)
        # Return a helpful fallback response
        return "I encountered a technical issue while analyzing your request. Let me know if you'd like to continue with a simpler approach or if you have any specific questions about creating your agent."
    except RateLimitError as e:
        logger.error(f"OpenAI Rate Limit Error: {str(e)}")
        return "I'm currently experiencing high demand. Please try again in a moment."
    except APIConnectionError as e:
        logger.error(f"OpenAI API Connection Error: {str(e)}")
        return "I'm having trouble connecting to my services. Please check your internet connection and try again."
    except Exception as e:
        logger.error(f"Unexpected error in reasoning agent: {str(e)}", exc_info=True)
        logger.error(f"Traceback: {traceback.format_exc()}")
        return "I'm having trouble analyzing your requirements right now. Based on what you've shared, I understand you want to create a tool-using agent. Could you provide more details about what specific systems it should interact with?"

# For regular (non-reasoning) agent prompt optimization during conversation
async def optimize_regular_prompt(prompt: str) -> str:
    """
    Optimize a user prompt for the regular (non-reasoning) agent path during the conversation phase.
    This function generates follow-up questions based on the specific services mentioned.
    """
    logger.info(f"Optimizing regular conversation prompt: {prompt[:50]}...")
    
    system_prompt = """
    You are a helpful assistant tasked with gathering information for an agent creation task.
    Your goal is to ask specific, relevant follow-up questions based on what the user has already shared.

    Important guidelines:
    1. Identify which systems or services the user mentioned (Google Drive, Slack, email, etc.)
    2. Ask ONLY about those specific services - NEVER mention services they didn't reference
    3. Acknowledge what they've already told you
    4. Ask 1-2 specific questions about:
       - Authentication/access details for mentioned services
       - Data processing requirements
       - Delivery/output format preferences
    5. Be conversational and natural, avoid generic or templated responses
    6. Vary your questions based on the specific context
    
    For example:
    - If they mention Google Drive, ask about document identification or permissions
    - If they mention email, ask about recipients or formatting
    - Always tailor your questions to their specific request
    """
    
    try:
        # Check for conversation format
        is_conversation = "You:" in prompt or "Assistant:" in prompt
        
        # Extract the latest user message from conversation if needed
        user_prompt = prompt
        if is_conversation:
            try:
                lines = prompt.split('\n')
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].startswith("You:"):
                        user_prompt = lines[i][4:].strip()
                        break
                logger.info(f"Extracted latest user message: {user_prompt[:50]}...")
            except Exception as e:
                logger.error(f"Error extracting user message: {str(e)}", exc_info=True)
                # Continue with the original prompt if extraction fails
        
        # Improved API call with additional error handling
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5,
                timeout=30,  # Add timeout
            )
            
            result = response.choices[0].message.content.strip()
            logger.info(f"Regular prompt optimization response: {result[:100]}...")
            return result
        except (APIError, RateLimitError, APIConnectionError) as api_e:
            logger.error(f"OpenAI API specific error: {str(api_e)}", exc_info=True)
            # Create a contextual fallback response
            if "google drive" in user_prompt.lower() and "email" in user_prompt.lower():
                return "Thanks for providing those details about the Google Drive document and email requirements. Do you have any specific formatting requirements for the summary, or should I use a standard format?"
            elif "google drive" in user_prompt.lower():
                return "I understand you want to work with Google Drive. Can you tell me more about what specific operations you need to perform with the documents?"
            elif "email" in user_prompt.lower():
                return "I see you mentioned email functionality. Could you specify who should receive these emails and if there are any particular formatting requirements?"
            else:
                return "Thanks for providing those details. Do you have any specific requirements for how the agent should process or present the information?"
    except Exception as e:
        logger.error(f"Error in optimize_regular_prompt: {str(e)}", exc_info=True)
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Provide a generic but helpful response
        return "Thank you for sharing those details. I think I have what I need to help create your agent. Is there anything specific about authentication or data handling that you'd like to mention before we proceed?"

# Final optimization for submission to Claude
async def real_optimize_prompt(prompt: str) -> str:
    """
    Final optimization of a user prompt for Claude to generate tool-using agents.
    This creates a structured, detailed prompt specifically formatted for Claude's tool-use capabilities.
    """
    logger.info(f"Final optimization for Claude tool use: {prompt[:100]}...")
    
    system_prompt = """
    You are a prompt optimizer specializing in Claude's tool-use capabilities. Your task is to transform user requests
    into well-structured prompts that will help Claude generate effective tool-using Python agents.

    Follow this exact structure in your response:

    1. TASK OVERVIEW
    [Write a clear, concise description of what the agent needs to do based on the user's request]

    2. REQUIRED CAPABILITIES
    [List all systems, APIs, and services the agent will need to interact with]

    3. IMPLEMENTATION REQUIREMENTS
    [Provide specific details about how the agent should work, including authentication, data handling, and error management]

    4. OUTPUT REQUIREMENTS
    [Specify what the agent should return or how it should present results]

    5. TOOL-USE FORMAT
    [Explicitly instruct Claude to implement this using the Claude tool-use format as documented at 
    https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview]

    IMPORTANT GUIDELINES:
    - Do NOT explain or add commentary outside the structured sections
    - Be specific and detailed but concise
    - Focus only on what Claude needs to know to create the agent
    - Do not make assumptions about services that weren't mentioned, but do include all necessary components
    - Ensure all requirements are clear and actionable
    - Format with clean, numbered lists for readability
    """
    
    try:
        # Extract conversation details if needed
        extracted_prompt = prompt
        if "You:" in prompt and "Assistant:" in prompt:
            try:
                # Reconstruct the full conversation context
                lines = prompt.split('\n')
                conversation_text = []
                
                for line in lines:
                    if line.startswith("You:") or line.startswith("Assistant:"):
                        conversation_text.append(line)
                    elif conversation_text and line.strip():
                        conversation_text[-1] += " " + line.strip()
                
                # Create a summarized version of the conversation
                extracted_prompt = "User Requirements Summary:\n"
                for line in conversation_text:
                    if line.startswith("You:"):
                        extracted_prompt += "- " + line[4:].strip() + "\n"
                
                logger.info(f"Extracted conversation summary: {extracted_prompt[:100]}...")
            except Exception as e:
                logger.error(f"Error extracting conversation: {str(e)}", exc_info=True)
                # Continue with original prompt if extraction fails
        
        # Call the API with improved error handling
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": extracted_prompt}
                ],
                temperature=0.3,
                timeout=45,  # Add timeout for longer processing
            )
            
            result = response.choices[0].message.content.strip()
            logger.info(f"Final optimization result: {result[:100]}...")
            return result
        except (APIError, RateLimitError, APIConnectionError) as api_e:
            logger.error(f"OpenAI API error in final optimization: {str(api_e)}", exc_info=True)
            
            # Create a structured fallback response based on detected keywords
            prompt_lower = extracted_prompt.lower()
            has_drive = "drive" in prompt_lower or "google" in prompt_lower or "document" in prompt_lower
            has_email = "email" in prompt_lower or "mail" in prompt_lower or "gmail" in prompt_lower
            
            fallback = """
1. TASK OVERVIEW
Create a Python agent that interacts with specified services to automate a workflow.

2. REQUIRED CAPABILITIES
"""
            if has_drive:
                fallback += "- Google Drive API for document access and manipulation\n"
            if has_email:
                fallback += "- Email sending capability via SMTP or other email API\n"
            
            fallback += """
3. IMPLEMENTATION REQUIREMENTS
- Implement secure authentication for all services
- Include error handling and retries for API calls
- Log all operations for debugging and audit purposes

4. OUTPUT REQUIREMENTS
- Provide clear success/error messages
- Return structured results in a consistent format

5. TOOL-USE FORMAT
Implement this using Claude's tool-use format to create a well-structured agent with proper function definitions and clear documentation.
"""
            return fallback
    except Exception as e:
        logger.error(f"Error in final optimization: {str(e)}", exc_info=True)
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Create a generic but structured fallback
        return """
1. TASK OVERVIEW
Create a Python agent that automates the requested workflow based on the user's requirements.

2. REQUIRED CAPABILITIES
- Access to necessary APIs and services
- Data processing functionality
- Output delivery mechanism

3. IMPLEMENTATION REQUIREMENTS
- Implement proper authentication and security
- Include comprehensive error handling
- Create modular, maintainable code

4. OUTPUT REQUIREMENTS
- Return results in the specified format
- Provide clear status updates and error messages

5. TOOL-USE FORMAT
Implement this using Claude's tool-use format to create a well-structured agent with proper function definitions and clear documentation.
"""