# app/core/ws_auth.py
from jose import jwt
from jose.exceptions import JWTError
from fastapi import HTTPException, status
import requests
import time
from typing import Dict, Any
import logging

# Cache the JWKS data to avoid frequent HTTP requests
JWKS_CACHE = {}
JWKS_CACHE_TIME = 0
JWKS_CACHE_TTL = 3600  # Cache for 1 hour

async def verify_ws_jwt(token: str) -> Dict[str, Any]:
    """Verify Auth0 JWT token and return its payload."""
    try:
        # 1. Get the public key from Auth0
        jwks = await get_jwks()
        
        # 2. Get the key ID from the token header
        unverified_header = jwt.get_unverified_header(token)
        if not unverified_header.get("kid"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token header. No 'kid' found.",
            )
        
        # 3. Find the matching key in JWKS
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break
                
        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find appropriate key.",
            )
        
        # 4. Verify and decode the token
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience="https://workflow-automation-api",  # Replace with your Auth0 API identifier
            issuer=f"https://dev-8qsl0ztjfq1yokoo.us.auth0.com/",  # Added https:// and trailing slash
        )
        
        # 5. Additional validation if needed
        return payload
        
    except JWTError as e:
        logging.error(f"JWT validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}",
        )
    except Exception as e:
        logging.error(f"Unexpected error in token validation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

async def get_jwks():
    """Get the JWKS from Auth0 with caching."""
    global JWKS_CACHE, JWKS_CACHE_TIME
    
    # Return cached JWKS if it's still valid
    current_time = time.time()
    if JWKS_CACHE and (current_time - JWKS_CACHE_TIME) < JWKS_CACHE_TTL:
        return JWKS_CACHE
    
    # Fetch new JWKS
    jwks_url = f"https://dev-8qsl0ztjfq1yokoo.us.auth0.com/.well-known/jwks.json"  # Replace with your Auth0 domain
    response = requests.get(jwks_url)
    response.raise_for_status()
    
    # Update cache
    JWKS_CACHE = response.json()
    JWKS_CACHE_TIME = current_time
    
    return JWKS_CACHE