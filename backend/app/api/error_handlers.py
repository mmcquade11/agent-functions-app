from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

logger = logging.getLogger(__name__)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle validation errors.
    """
    error_details = []
    
    for error in exc.errors():
        error_details.append({
            "loc": error.get("loc", []),
            "msg": error.get("msg", ""),
            "type": error.get("type", "")
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": error_details,
            "message": "Validation error"
        }
    )


async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle general exceptions.
    """
    # Log the error
    logger.error(
        f"Unhandled exception: {str(exc)}",
        exc_info=True,
        extra={"request_path": request.url.path}
    )
    
    # Return a generic error response
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "message": "An unexpected error occurred",
            "detail": str(exc) if __debug__ else "Internal server error"
        }
    )
