from fastapi import APIRouter

from app.api.v1.endpoints import workflows, executions, schedules, logs, audit, prompt
from app.api.v1 import healthcheck

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


