from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from uuid import uuid4

from app.db.base import Base


class Workflow(Base):
    """Workflow database model."""
    
    __tablename__ = "workflows"
    __table_args__ = {'extend_existing': True}
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    workflow_definition = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True)
    is_scheduled = Column(Boolean, default=False)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    
    # Relationships
    executions = relationship("WorkflowExecution", back_populates="workflow", cascade="all, delete-orphan")
    schedules = relationship("WorkflowSchedule", back_populates="workflow", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Workflow {self.name}>"


class WorkflowExecution(Base):
    """Workflow execution database model."""
    
    __tablename__ = "workflow_executions"
    __table_args__ = {'extend_existing': True}
    
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


class WorkflowSchedule(Base):
    """Workflow schedule database model."""
    
    __tablename__ = "workflow_schedules"
    __table_args__ = {'extend_existing': True}
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    workflow_id = Column(String, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    cron_expression = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    name = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    execution_inputs = Column(JSON, nullable=True)
    timezone = Column(String, nullable=False, default="UTC")
    
    # Relationships
    workflow = relationship("Workflow", back_populates="schedules")
    
    def __repr__(self):
        return f"<WorkflowSchedule {self.name or self.id}>"


class ExecutionLog(Base):
    """Execution log database model."""
    
    __tablename__ = "execution_logs"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True)
    execution_id = Column(String, ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    level = Column(String, nullable=False, default="INFO")  # INFO, WARNING, ERROR, DEBUG
    message = Column(Text, nullable=False)
    step_id = Column(String, nullable=True)
    step_name = Column(String, nullable=True)
    log_metadata = Column(JSON, nullable=True)  # <== renamed from metadata to log_metadata
    
    # Relationships
    execution = relationship("WorkflowExecution", back_populates="logs")
    
    def __repr__(self):
        return f"<ExecutionLog {self.id} [{self.level}]>"

