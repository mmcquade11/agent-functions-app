from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.services.scheduler import scheduler_lifespan
from contextlib import asynccontextmanager

from app.api.v1.router import api_router
from app.core.config import settings
from app.api.error_handlers import validation_exception_handler, general_exception_handler
from app.websockets.routes import setup_websocket_routes
from app.db.session import engine
from app.db.base import Base
from app.tasks.worker import create_celery
from app.services.scheduler import scheduler_instance



from sqlalchemy.ext.asyncio import AsyncEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initialize Celery
    app.celery_app = create_celery()
    # Start Scheduler
    await scheduler_instance.start()

    yield

    # On shutdown
    await scheduler_instance.stop()

    # Clean up resources when shutting down
    # (Optional) Close DB sessions, shutdown tasks, etc.


def create_application() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
        lifespan=lifespan,
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    )

    # Set up CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    # Include routers
    app.include_router(api_router, prefix=settings.API_V1_STR)
    
    # Set up WebSocket routes
    setup_websocket_routes(app)

    @app.get("/health", include_in_schema=False)
    async def health_check():
        return JSONResponse(content={"status": "ok"}, status_code=200)

    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT != "production",
    )
