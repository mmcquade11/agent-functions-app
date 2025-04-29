from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


# Convert PostgreSQL URL to AsyncPG URL
SQLALCHEMY_DATABASE_URL = str(settings.DATABASE_URI).replace(
    "postgresql+psycopg2://", 
    "postgresql+asyncpg://"
)

# Create async engine
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.ENVIRONMENT == "development",
)

# Create async session factory
SessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autocommit=False, 
    autoflush=False
)


async def get_db():
    """
    Dependency function to get a DB session.
    Yields a session that is automatically closed when the context ends.
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
