from sqlalchemy import Column, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base_class import Base  # ✅ required for Alembic

class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(String, nullable=False, index=True)
    original_prompt = Column(Text, nullable=False)
    optimized_prompt = Column(Text, nullable=True)
    needs_reasoning = Column(String, nullable=False, default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
