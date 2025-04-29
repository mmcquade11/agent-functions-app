from typing import List, Union, Dict, Any, Optional
from pydantic import PostgresDsn, validator, field_validator
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
    POSTGRES_SERVER: str = "localhost"  # Add default value
    POSTGRES_USER: str = "postgres"  # Add default value
    POSTGRES_PASSWORD: str = "postgres"  # Add default value
    POSTGRES_DB: str = "workflow_automation"  # Add default value
    POSTGRES_PORT: str = "5432"
    DATABASE_URI: Optional[PostgresDsn] = None
    
    @field_validator("DATABASE_URI", mode="before")
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        
        return PostgresDsn.build(
            scheme="postgresql+psycopg2",
            username=values.data["POSTGRES_USER"],
            password=values.data["POSTGRES_PASSWORD"],
            host=values.data["POSTGRES_SERVER"],
            port=int(values.data["POSTGRES_PORT"]),  # Convert to integer
            path=f"{values.data['POSTGRES_DB'] or ''}",
        )
    
    # Auth0 Settings
    AUTH0_DOMAIN: str
    AUTH0_AUDIENCE: Union[str, List[str]]
    AUTH0_ALGORITHMS: List[str] = ["RS256"]
    AUTH0_ISSUER: Optional[str] = None

    
    @field_validator("AUTH0_ISSUER", mode="before")
    def assemble_auth0_issuer(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if v is not None:
            return v
        return f"https://{values.data['AUTH0_DOMAIN']}/"
    
    # Redis Settings (for WebSockets and Celery)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_URI: Optional[str] = None
    
    @field_validator("REDIS_URI", mode="before")
    def assemble_redis_connection(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if isinstance(v, str):
            return v
            
        if values.data.get("REDIS_PASSWORD"):
            return f"redis://:{values.data['REDIS_PASSWORD']}@{values.data['REDIS_HOST']}:{values.data['REDIS_PORT']}/0"
        
        return f"redis://{values.data['REDIS_HOST']}:{values.data['REDIS_PORT']}/0"
    
    # Celery Settings
    CELERY_BROKER_URL: str = None
    
    @field_validator("CELERY_BROKER_URL", mode="before")
    def assemble_celery_broker_url(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if isinstance(v, str):
            return v
            
        return values.data["REDIS_URI"]



    # Conductor (Auto-Reasoning, Auto-tools)
    CONDUCTOR_BASE_URL: str
    ARCEE_CONDUCTOR_SYSTEM_TOKEN: str

    # GPT-4o (Prompt Optimizer)
    OPENAI_BASE_URL: str
    OPENAI_API_KEY: str

    # Claude 3.7 (Agent Code Generator)
    CLAUDE_BASE_URL: str
    CLAUDE_API_KEY: str


# Create settings instance
settings = Settings()