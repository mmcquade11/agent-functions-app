# app/main.py (modified)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager

from app.api.v1.router import api_router
from app.api.error_handlers import validation_exception_handler, general_exception_handler
from app.db.session import engine
from app.db.base import Base
from app.tasks.worker import create_celery
from app.services.scheduler import scheduler_instance
from app.websocket_app import ws_app  # Import the WebSocket app

# Add this to your app/main.py file, right after defining the app and before mounting any routers

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.celery_app = create_celery()
    await scheduler_instance.start()
    yield
    await scheduler_instance.stop()

def create_application() -> FastAPI:
    app = FastAPI(
        title="Agent Function App",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173","null", None],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    app.include_router(api_router, prefix="/api/v1")
    
    # Mount the WebSocket app at the /ws path
    app.mount("/ws", ws_app)

    @app.get("/health", include_in_schema=False)
    async def health_check():
        return JSONResponse(content={"status": "ok"}, status_code=200)

    return app

app = create_application()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)