from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from sqlalchemy.sql import func
from uuid import uuid4

from app.db.base import Base


class AuditLog(Base):
    """Audit log database model for tracking user actions."""
    
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    event_type = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    resource_data = Column(JSON, nullable=False)  # JSON data about the affected resource
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    
    def __repr__(self):
        return f"<AuditLog {self.id} ({self.event_type})>"
