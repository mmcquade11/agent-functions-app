from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class ExecutionLog(Base):
    """Execution log database model."""
    
    __tablename__ = "execution_logs"
    
    id = Column(Integer, primary_key=True)
    execution_id = Column(String, ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    level = Column(String, nullable=False, default="INFO")  # INFO, WARNING, ERROR, DEBUG
    message = Column(Text, nullable=False)
    step_id = Column(String, nullable=True)
    step_name = Column(String, nullable=True)
    metadata = Column(JSON, nullable=True)
    
    # Relationships
    execution = relationship("WorkflowExecution", back_populates="logs")
    
    def __repr__(self):
        return f"<ExecutionLog {self.id} [{self.level}]>"