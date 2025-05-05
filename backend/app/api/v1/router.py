# app/api/v1/router.py

from fastapi import APIRouter

from app.api.v1.endpoints import workflows, executions, schedules, logs, audit, prompt, agents, reasoning_agent
from app.api.v1 import healthcheck
# Import the agents_router from the correct location
from app.agents.agent_router import agents_router

# Create main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(workflows.router, prefix="/workflows", tags=["Workflows"])
api_router.include_router(executions.router, prefix="/executions", tags=["Executions"])
api_router.include_router(schedules.router, prefix="/schedules", tags=["Schedules"])
api_router.include_router(logs.router, prefix="/logs", tags=["Logs"])
api_router.include_router(audit.router, prefix="/admin/audit", tags=["Admin"])
api_router.include_router(healthcheck.router, prefix="")
api_router.include_router(prompt.router, prefix="/prompt", tags=["Prompt"])
api_router.include_router(reasoning_agent.router, prefix="/agents", tags=["Agents"])
api_router.include_router(agents.router, prefix="/agents", tags=["Agents"])

# Include the new agent router
api_router.include_router(agents_router, prefix="/agents/v2", tags=["Agents"])