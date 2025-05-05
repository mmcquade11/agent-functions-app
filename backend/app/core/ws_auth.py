# app/core/ws_auth.py

import jwt
from fastapi import HTTPException, status
import logging
from app.core.config import settings
import traceback
import time

# Set up logging
logger = logging.getLogger(__name__)

async def verify_ws_jwt(token: str):
    """
    Verify the JWT token from the WebSocket connection.
    Returns the decoded payload if valid, raises an exception otherwise.
    """
    logger.info(f"Verifying WebSocket JWT token: {token[:20]}...")
    
    try:
        # Get the Auth0 public key/secret from settings
        secret_or_pub_key = settings.AUTH0_PUBLIC_KEY
        
        # Options for verification
        options = {
            'verify_signature': True,  # Verify signature
            'verify_exp': True,        # Verify expiration
            'verify_iss': True,        # Verify issuer
            'verify_aud': True,        # Verify audience
        }
        
        # Try to decode the token with the Auth0 settings
        payload = jwt.decode(
            token,
            secret_or_pub_key,
            algorithms=['RS256'],
            options=options,
            audience=settings.AUTH0_API_AUDIENCE,
            issuer=settings.AUTH0_ISSUER,
        )
        
        logger.info(f"Successfully verified WebSocket JWT token")
        
        # If verification passed, return the decoded payload
        return payload
        
    except Exception as e:
        logger.error(f"Error verifying WebSocket JWT: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # More detailed error logging for debugging
        try:
            # Try to decode the token without verification for debugging
            unverified_payload = jwt.decode(
                token, 
                options={"verify_signature": False}, 
                algorithms=['RS256']
            )
            logger.error(f"Token payload (unverified): {unverified_payload}")
            
            # Check specific potential issues
            if 'exp' in unverified_payload and unverified_payload['exp'] < time.time():
                logger.error("Token appears to be expired")
            if 'aud' in unverified_payload and settings.AUTH0_API_AUDIENCE not in unverified_payload['aud']:
                logger.error(f"Token audience mismatch: got {unverified_payload['aud']}, expected {settings.AUTH0_API_AUDIENCE}")
            if 'iss' in unverified_payload and unverified_payload['iss'] != settings.AUTH0_ISSUER:
                logger.error(f"Token issuer mismatch: got {unverified_payload['iss']}, expected {settings.AUTH0_ISSUER}")
        except Exception as debug_e:
            logger.error(f"Error debugging token: {str(debug_e)}")
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication error"
        )