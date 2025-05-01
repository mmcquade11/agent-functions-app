# app/websocket_app.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from typing import Dict, Any, AsyncGenerator
import logging

from app.core.ws_auth import verify_ws_jwt
from app.services.tool_init import registry
from app.services.claude_runner import stream_claude_tool_use

# Create a separate FastAPI instance for WebSockets
ws_app = FastAPI()

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
            # Verify the token
            user_payload = await verify_ws_jwt(token)
            logging.info(f"✅ Authentication successful for user: {user_payload.get('sub')}")
            
            # Get the prompt from the client
            data = await websocket.receive_json()
            user_prompt = data.get("prompt")
            logging.info(f"📥 Received prompt: {user_prompt[:50]}...")
            
            # Process with Claude
            async for update in stream_claude_tool_use(user_prompt, registry):
                await websocket.send_json(update)
                
            await websocket.send_json({"type": "done", "phase": "done"})
            
        except Exception as e:
            logging.error(f"❌ Authentication or processing error: {str(e)}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            
    except WebSocketDisconnect:
        logging.info("⚠️ WebSocket disconnected by client")
    except Exception as e:
        logging.error(f"❌ Unhandled WebSocket error: {str(e)}")