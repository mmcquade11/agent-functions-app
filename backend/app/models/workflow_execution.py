from sqlalchemy import Column, String, Text, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from uuid import uuid4

from app.db.base import Base


class WorkflowExecution(Base):
    """Workflow execution database model."""
    
    __tablename__ = "workflow_executions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    workflow_id = Column(String, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, nullable=False, index=True, default="pending")  # pending, running, completed, failed
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    execution_inputs = Column(JSON, nullable=True)
    execution_outputs = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    executed_by = Column(String, nullable=False)
    
    # Relationships
    workflow = relationship("Workflow", back_populates="executions")
    logs = relationship("ExecutionLog", back_populates="execution", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<WorkflowExecution {self.id} ({self.status})>"