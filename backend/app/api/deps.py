from typing import Generator
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.core.auth import JWTBearer, TokenPayload, get_current_user

async def require_admin(user: TokenPayload = Depends(get_current_user)):
    """
    Dependency that requires the user to be an admin.
    """
    if "admin:access" not in (user.permissions or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user

def require_permissions(required_permissions: list[str]):
    """
    Dependency for requiring specific permissions.
    """
    def _require_permissions(user: TokenPayload = Depends(get_current_user)):
        missing = [p for p in required_permissions if p not in user.permissions]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {', '.join(missing)}",
            )
        return user
    return _require_permissions

async def get_db() -> Generator:
    """
    Dependency for getting DB session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        await db.close()

async def get_client_info(request: Request) -> dict:
    """
    Dependency for getting client info (IP, user agent).
    """
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent")
    }

# Re-export authentication dependencies
auth = JWTBearer()
