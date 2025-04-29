# app/websockets/manager.py

from typing import Dict, Set, Optional
import logging
from fastapi import WebSocket
import asyncio
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    WebSocket connection manager for real-time workflow execution logs.
    Manages active connections grouped by execution run ID.
    """
    
    def __init__(self):
        """Initialize the WebSocket manager."""
        # Dictionary mapping run_id to set of connected WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Lock to prevent race conditions when modifying connections
        self.lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, run_id: str) -> None:
        """
        Connect a client to a specific execution run's logs.
        
        Args:
            websocket (WebSocket): WebSocket connection
            run_id (str): Execution run ID
        """
        # Accept the websocket connection
        await websocket.accept()
        
        # Add to active connections for this run_id
        async with self.lock:
            if run_id not in self.active_connections:
                self.active_connections[run_id] = set()
            self.active_connections[run_id].add(websocket)
        
        logger.info(f"Client connected to execution logs for run ID: {run_id}")
    
    async def disconnect(self, websocket: WebSocket, run_id: str) -> None:
        """
        Disconnect a client from a specific execution run's logs.
        
        Args:
            websocket (WebSocket): WebSocket connection
            run_id (str): Execution run ID
        """
        async with self.lock:
            if run_id in self.active_connections:
                self.active_connections[run_id].discard(websocket)
                
                # Clean up empty connection sets
                if not self.active_connections[run_id]:
                    del self.active_connections[run_id]
        
        logger.info(f"Client disconnected from execution logs for run ID: {run_id}")
    
    async def broadcast_log(
        self, 
        run_id: str, 
        log_data: Dict
    ) -> None:
        """
        Broadcast a log message to all clients connected to a specific execution run.
        
        Args:
            run_id (str): Execution run ID
            log_data (Dict): Log data to broadcast
        """
        if run_id not in self.active_connections:
            return
        
        # Add timestamp if not present
        if "timestamp" not in log_data:
            log_data["timestamp"] = datetime.utcnow().isoformat()
        
        # Ensure run_id is included in the message
        log_data["run_id"] = run_id
        
        # List to track disconnected clients
        disconnected = set()
        
        # Send message to all connected clients
        for websocket in self.active_connections[run_id]:
            try:
                await websocket.send_json(log_data)
            except Exception as e:
                logger.error(f"Error sending log to client: {str(e)}")
                disconnected.add(websocket)
        
        # Clean up disconnected clients
        if disconnected:
            async with self.lock:
                if run_id in self.active_connections:
                    self.active_connections[run_id] -= disconnected
                    
                    # Clean up empty connection sets
                    if not self.active_connections[run_id]:
                        del self.active_connections[run_id]
    
    async def broadcast_run_completion(self, run_id: str, success: bool) -> None:
        """
        Broadcast run completion and close all connections for this run.
        
        Args:
            run_id (str): Execution run ID
            success (bool): Whether the execution completed successfully
        """
        if run_id not in self.active_connections:
            return
        
        # Create completion message
        completion_message = {
            "type": "run_completed",
            "run_id": run_id,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Get all connections for this run
        connections = list(self.active_connections.get(run_id, set()))
        
        # Send completion message and close connections
        for websocket in connections:
            try:
                await websocket.send_json(completion_message)
                await websocket.close(code=1000)  # Normal closure
            except Exception as e:
                logger.error(f"Error closing WebSocket connection: {str(e)}")
        
        # Remove all connections for this run
        async with self.lock:
            if run_id in self.active_connections:
                del self.active_connections[run_id]

# Create a global instance of the WebSocket manager
websocket_manager = WebSocketManager()