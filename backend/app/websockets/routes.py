from fastapi import WebSocket, WebSocketDisconnect, Depends, status, HTTPException, FastAPI, Query
from app.websockets import ws_execute_agent
import asyncio
import logging
from typing import Optional

from app.websockets.manager import websocket_manager
from app.core.auth import JWTBearer, get_current_user
from app.core.config import settings
#from app.services.workflow import get_workflow_execution

logger = logging.getLogger(__name__)

def setup_websocket_routes(app: FastAPI):
    app.include_router(ws_execute_agent.router)

# Custom WebSocket authentication middleware
async def get_token_from_query(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """Extract and validate JWT token from WebSocket query parameters."""
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    
    # Validate token using the JWTBearer
    jwt_bearer = JWTBearer()
    try:
        payload = await jwt_bearer.verify_jwt(token)
        return payload
    except HTTPException as e:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise e


async def handle_execution_logs(websocket: WebSocket, execution_id: str, token_payload: dict):
    """
    Handle WebSocket connection for streaming execution logs.
    """
    try:
        # Verify execution exists and user has access
        #execution = await get_workflow_execution(execution_id, token_payload)
        #if not execution:
            #await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            #return
        
        # Connect to the manager
        await websocket_manager.connect(websocket, execution_id)
        
        # Send initial connection message
        await websocket_manager.send_message(
            websocket, 
            f"Connected to execution logs for {execution_id}"
        )
        
        # Keep connection open and handle messages
        try:
            while True:
                # This will keep the connection open
                # We don't actually process incoming messages, but we need to handle them
                data = await websocket.receive_text()
                # Optionally process commands from the client
        except WebSocketDisconnect:
            # Client disconnected, clean up
            await websocket_manager.disconnect(websocket, execution_id)
        
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {str(e)}")
        await websocket_manager.send_message(
            websocket, 
            f"Error: {str(e)}", 
            message_type="error"
        )
        await websocket_manager.disconnect(websocket, execution_id)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass


def setup_websocket_routes(app: FastAPI):
    """Set up WebSocket routes for the application."""
    
    @app.websocket("/ws/executions/{execution_id}/logs")
    async def execution_logs(
        websocket: WebSocket, 
        execution_id: str,
        token_payload: dict = Depends(get_token_from_query)
    ):
        """WebSocket endpoint for real-time execution logs."""
        await handle_execution_logs(websocket, execution_id, token_payload)
