from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncAttrs

# Create a base class for SQLAlchemy models
Base = declarative_base(cls=AsyncAttrs)
