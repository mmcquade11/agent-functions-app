from typing import Dict, List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from jose.exceptions import JWTError
import httpx
from pydantic import BaseModel

from app.core.config import settings


class JWKS:
    """JSON Web Key Set handler for Auth0 JWT validation."""
    
    def __init__(self, domain: str):
        self.domain = domain
        self.jwks_uri = f"https://{domain}/.well-known/jwks.json"
        self.jwks: Optional[Dict] = None
        
    async def get_jwks(self) -> Dict:
        """Fetch the JSON Web Key Set from Auth0."""
        if self.jwks is None:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.jwks_uri)
                response.raise_for_status()
                self.jwks = response.json()
        return self.jwks
        
    async def get_key(self, kid: str) -> Dict:
        """Get the key matching the provided key ID."""
        jwks = await self.get_jwks()
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return key
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to find appropriate key",
        )


class JWTBearer(HTTPBearer):
    """JWT Bearer authentication dependency."""
    
    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)
        self.jwks = JWKS(settings.AUTH0_DOMAIN)
        
    async def __call__(self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
        """Validate the provided JWT token."""
        if credentials.scheme != "Bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme",
            )
            
        payload = await self.verify_jwt(credentials.credentials)
        return payload
        
    async def verify_jwt(self, jwt_token: str) -> Dict:
        """Verify the JWT token using Auth0 keys."""
        try:
            # Get the unverified header to extract the key ID
            unverified_header = jwt.get_unverified_header(jwt_token)
            kid = unverified_header.get("kid")
            if not kid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Key ID not found in token header",
                )
                
            # Get the key from JWKS
            key = await self.jwks.get_key(kid)
                
            # Decode and verify the token
            payload = jwt.decode(
                jwt_token,
                key,
                algorithms=settings.AUTH0_ALGORITHMS,
                audience=settings.AUTH0_AUDIENCE,
                issuer=settings.AUTH0_ISSUER,
            )
            
            return payload
            
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
            )
        
from typing import Optional, List, Union
from pydantic import BaseModel

class TokenPayload(BaseModel):
    """Model representing the JWT token payload."""
    sub: str
    permissions: Optional[List[str]] = []
    iss: Optional[str] = None
    aud: Optional[Union[str, List[str]]] = None
    exp: Optional[int] = None

    class Config:
        extra = "allow"  # <-- THIS is critical!


# Dependencies for authentication and authorization
auth = JWTBearer()

from app.core.auth import TokenPayload
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())) -> TokenPayload:
    auth = JWTBearer()
    payload_dict = await auth(credentials)

    try:
        user = TokenPayload(
            sub=payload_dict.get("sub"),
            permissions=payload_dict.get("permissions", []),
            iss=payload_dict.get("iss"),
            aud=payload_dict.get("aud"),
            exp=payload_dict.get("exp"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token payload structure: {str(e)}",
        )

    return user


