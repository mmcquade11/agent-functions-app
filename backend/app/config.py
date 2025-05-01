from typing import List, Union, Dict, Any, Optional
from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)
    
    # App Settings
    PROJECT_NAME: str = "Workflow Automation API"
    PROJECT_DESCRIPTION: str = "API for workflow automation with real-time logging"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    
    # CORS Settings
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Database Settings
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "workflow_automation"
    POSTGRES_PORT: str = "5432"
    DATABASE_URI: Optional[PostgresDsn] = None
    
    @field_validator("DATABASE_URI", mode="before")
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        
        return PostgresDsn.build(
            scheme="postgresql+psycopg2",
            username=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_SERVER"),
            port=values.get("POSTGRES_PORT"),
            path=f"{values.get('POSTGRES_DB') or ''}",
        )
    ASYNC_DATABASE_URI: str = None
    SQLALCHEMY_DATABASE_URI: str = None  # sync version for Alembic

    @field_validator("ASYNC_DATABASE_URI", mode="before")
    def build_async_uri(cls, v, values):
        return (
            f"postgresql+asyncpg://{values.data['POSTGRES_USER']}:{values.data['POSTGRES_PASSWORD']}"
            f"@{values.data['POSTGRES_SERVER']}:{values.data['POSTGRES_PORT']}/{values.data['POSTGRES_DB']}"
        )

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    def build_sqlalchemy_uri(cls, v, values):
        return (
            f"postgresql+psycopg2://{values.data['POSTGRES_USER']}:{values.data['POSTGRES_PASSWORD']}"
            f"@{values.data['POSTGRES_SERVER']}:{values.data['POSTGRES_PORT']}/{values.data['POSTGRES_DB']}"
        )

    
    # Auth0 Settings
    AUTH0_DOMAIN: str
    AUTH0_AUDIENCE: str
    AUTH0_ALGORITHMS: List[str] = ["RS256"]
    AUTH0_ISSUER: Optional[str] = None  

    
    @field_validator("AUTH0_ISSUER", mode="before")
    def assemble_auth0_issuer(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if v is not None:
            return v
        return f"https://{values.get('AUTH0_DOMAIN')}/"
    
    # Redis Settings (for WebSockets and Celery)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_URI: Optional[str] = None
    
    @field_validator("REDIS_URI", mode="before")
    def assemble_redis_connection(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if isinstance(v, str):
            return v
            
        if values.get("REDIS_PASSWORD"):
            return f"redis://:{values.get('REDIS_PASSWORD')}@{values.get('REDIS_HOST')}:{values.get('REDIS_PORT')}/0"
        
        return f"redis://{values.get('REDIS_HOST')}:{values.get('REDIS_PORT')}/0"
    
    # Celery Settings
    CELERY_BROKER_URL: Optional[str] = None
    
    @field_validator("CELERY_BROKER_URL", mode="before")
    def assemble_celery_broker_url(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if isinstance(v, str) and v:
            return v
            
        return values.get("REDIS_URI")


# Create settings instance
settings = Settings()