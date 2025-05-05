# app/websocket_app.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from typing import Dict, Any, AsyncGenerator
import json
import logging
import asyncio
import traceback

from app.core.ws_auth import verify_ws_jwt
# Fix import to use your session pattern
from app.db.session import get_db, SessionLocal
from app.agents.reasoning_agent import stream_reasoning_agent
from app.agents.regular_agent import stream_regular_agent
from app.services.tool_registry import ToolRegistry
from app.services.tool_init import registry
from app.services.enhanced_claude_runner import stream_enhanced_claude, identify_parameters

# Create a separate FastAPI instance for WebSockets
ws_app = FastAPI()
logger = logging.getLogger(__name__)

@ws_app.websocket("/execute-agent")
async def execute_agent_stream(websocket: WebSocket):
    logging.info("🟡 WebSocket connection attempt received")
    
    # Get token from query parameters
    token = websocket.query_params.get("token")
    if not token:
        logging.error("❌ No token provided in query parameters")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    try:
        # Accept the connection first
        await websocket.accept()
        logging.info("✅ WebSocket connection accepted")
        
        try:
            # Verify the token - with more robust error handling
            try:
                user_payload = await verify_ws_jwt(token)
                user_id = user_payload.get('sub')
                logging.info(f"✅ Authentication successful for user: {user_id}")
            except Exception as auth_err:
                logging.error(f"❌ Authentication error: {str(auth_err)}")
                await websocket.send_json({
                    "type": "error", 
                    "phase": "auth", 
                    "content": f"Authentication failed: {str(auth_err)}"
                })
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            
            # Get the prompt from the client
            try:
                data = await websocket.receive_json()
            except json.JSONDecodeError as json_err:
                logging.error(f"❌ Invalid JSON received: {str(json_err)}")
                await websocket.send_json({
                    "type": "error", 
                    "phase": "input", 
                    "content": "Invalid JSON data received"
                })
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                return
                
            prompt = data.get("prompt", "")
            needs_reasoning = data.get("needsReasoning", False)
            
            # New mode for parameter identification
            identify_params = data.get("identifyParameters", False)
            
            logging.info(f"📥 Received prompt: {prompt[:50]}...")
            logging.info(f"📥 Needs reasoning: {needs_reasoning}")
            logging.info(f"📥 Identify parameters: {identify_params}")
            
            # Validate the prompt
            if not prompt or not prompt.strip():
                logging.error("❌ Empty prompt received")
                await websocket.send_json({
                    "type": "error", 
                    "phase": "input", 
                    "content": "Empty prompt received"
                })
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                return
            
            # Create a database session using your pattern
            async with SessionLocal() as db:
                try:
                    # Choose the appropriate execution path
                    stream_generator = None
                    
                    if identify_params:
                        # Special path for parameter identification
                        logging.info("🔍 Using parameter identification mode")
                        stream_generator = identify_parameters(
                            prompt=prompt,
                            tool_registry=registry
                        )
                    elif needs_reasoning:
                        logging.info("🧠 Using reasoning agent")
                        stream_generator = stream_reasoning_agent(
                            original_prompt=prompt,
                            optimized_prompt=prompt,  # We assume the prompt is already optimized
                            db=db,
                            user_id=user_id
                        )
                    else:
                        logging.info("🤖 Using regular agent")
                        stream_generator = stream_regular_agent(
                            original_prompt=prompt,
                            optimized_prompt=prompt,  # We assume the prompt is already optimized
                            db=db,
                            user_id=user_id
                        )
                    
                    # Stream the results back to the client
                    async for chunk in stream_generator:
                        try:
                            await websocket.send_json(chunk)
                        except Exception as send_err:
                            logging.error(f"❌ Error sending chunk: {str(send_err)}")
                            # Try to continue with other chunks
                            continue
                    
                    # Send final message
                    await websocket.send_json({"type": "done", "phase": "done"})
                    
                    # Commit the session
                    await db.commit()
                except Exception as e:
                    # Rollback on error
                    await db.rollback()
                    logging.error(f"❌ Processing error: {str(e)}")
                    logging.error(f"❌ Traceback: {traceback.format_exc()}")
                    try:
                        await websocket.send_json({
                            "type": "error", 
                            "phase": "error", 
                            "content": f"Error processing request: {str(e)}"
                        })
                    except Exception:
                        # If we can't send the error, just log it
                        pass
                    raise
            
        except WebSocketDisconnect:
            logging.info("⚠️ WebSocket disconnected by client during processing")
        except Exception as e:
            logging.error(f"❌ Processing error: {str(e)}")
            logging.error(f"❌ Traceback: {traceback.format_exc()}")
            try:
                await websocket.send_json({
                    "type": "error", 
                    "phase": "error", 
                    "content": str(e)
                })
            except Exception:
                # If we can't send the error, just log it
                pass
            
    except WebSocketDisconnect:
        logging.info("⚠️ WebSocket disconnected by client")
    except Exception as e:
        logging.error(f"❌ Unhandled WebSocket error: {str(e)}")
        logging.error(f"❌ Traceback: {traceback.format_exc()}")