# app/api/v1/healthcheck.py

from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()

@router.get("/healthcheck", tags=["Health"])
async def healthcheck():
    """
    Basic health check endpoint to verify app configuration.
    """
    return {
        "auth0_domain": settings.AUTH0_DOMAIN,
        "auth0_audience": settings.AUTH0_AUDIENCE,
        "auth0_issuer": settings.AUTH0_ISSUER,
        "db_server": settings.POSTGRES_SERVER
    }
