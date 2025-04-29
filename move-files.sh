#!/bin/bash
# Simple script to move files from Downloads to the appropriate backend folder structure

# Set your downloads directory and backend directory
DOWNLOADS_DIR="/Users/markmcquade/Downloads"
BACKEND_DIR="backend"

# Make sure we're in the correct directory
if [ ! -d "$BACKEND_DIR" ]; then
  echo "Error: Backend directory not found. Please navigate to the parent directory of your backend folder."
  exit 1
fi

echo "Moving files from $DOWNLOADS_DIR to $BACKEND_DIR structure..."

# Core module files
if [ -f "$DOWNLOADS_DIR/config.py" ]; then
  echo "Moving config.py to app/core/config.py"
  cp "$DOWNLOADS_DIR/config.py" "$BACKEND_DIR/app/core/config.py"
fi

if [ -f "$DOWNLOADS_DIR/auth.py" ]; then
  echo "Moving auth.py to app/core/auth.py"
  cp "$DOWNLOADS_DIR/auth.py" "$BACKEND_DIR/app/core/auth.py"
fi

# Main app file
if [ -f "$DOWNLOADS_DIR/main.py" ]; then
  echo "Moving main.py to app/main.py"
  cp "$DOWNLOADS_DIR/main.py" "$BACKEND_DIR/app/main.py"
fi

# API module files
if [ -f "$DOWNLOADS_DIR/deps.py" ]; then
  echo "Moving deps.py to app/api/deps.py"
  cp "$DOWNLOADS_DIR/deps.py" "$BACKEND_DIR/app/api/deps.py"
fi

if [ -f "$DOWNLOADS_DIR/error_handlers.py" ]; then
  echo "Moving error_handlers.py to app/api/error_handlers.py"
  cp "$DOWNLOADS_DIR/error_handlers.py" "$BACKEND_DIR/app/api/error_handlers.py"
fi

if [ -f "$DOWNLOADS_DIR/router.py" ]; then
  echo "Moving router.py to app/api/v1/router.py"
  cp "$DOWNLOADS_DIR/router.py" "$BACKEND_DIR/app/api/v1/router.py"
fi

# API endpoint files
if [ -f "$DOWNLOADS_DIR/workflows.py" ]; then
  echo "Moving workflows.py to app/api/v1/endpoints/workflows.py"
  cp "$DOWNLOADS_DIR/workflows.py" "$BACKEND_DIR/app/api/v1/endpoints/workflows.py"
fi

# DB files
if [ -f "$DOWNLOADS_DIR/session.py" ]; then
  echo "Moving session.py to app/db/session.py"
  cp "$DOWNLOADS_DIR/session.py" "$BACKEND_DIR/app/db/session.py"
fi

if [ -f "$DOWNLOADS_DIR/base.py" ]; then
  echo "Moving base.py to app/db/base.py"
  cp "$DOWNLOADS_DIR/base.py" "$BACKEND_DIR/app/db/base.py"
fi

# Handle files with potentially multiple destinations
# For workflow.py and audit.py we need to check which one is which

# Look for workflow.py files
for file in "$DOWNLOADS_DIR"/workflow*.py; do
  if [ -f "$file" ]; then
    # Check if it contains model indicators
    if grep -q "class Workflow(Base)" "$file"; then
      echo "Moving $(basename "$file") to app/models/workflow.py"
      cp "$file" "$BACKEND_DIR/app/models/workflow.py"
    # Check if it contains schema indicators
    elif grep -q "class WorkflowBase" "$file"; then
      echo "Moving $(basename "$file") to app/schemas/workflow.py"
      cp "$file" "$BACKEND_DIR/app/schemas/workflow.py"
    else
      echo "Warning: Could not determine type of $(basename "$file")"
    fi
  fi
done

# Look for audit.py files
for file in "$DOWNLOADS_DIR"/audit*.py; do
  if [ -f "$file" ]; then
    # Check if it contains model indicators
    if grep -q "class AuditLog" "$file"; then
      echo "Moving $(basename "$file") to app/models/audit.py"
      cp "$file" "$BACKEND_DIR/app/models/audit.py"
    # Check if it contains service indicators
    elif grep -q "async def log_audit_event" "$file"; then
      echo "Moving $(basename "$file") to app/services/audit.py"
      cp "$file" "$BACKEND_DIR/app/services/audit.py"
    else
      echo "Warning: Could not determine type of $(basename "$file")"
    fi
  fi
done

# Look for executions.py files
for file in "$DOWNLOADS_DIR"/execution*.py; do
  if [ -f "$file" ]; then
    # Check if it contains API indicators
    if grep -q "APIRouter" "$file"; then
      echo "Moving $(basename "$file") to app/api/v1/endpoints/executions.py"
      cp "$file" "$BACKEND_DIR/app/api/v1/endpoints/executions.py"
    # Check if it contains task indicators
    elif grep -q "celery_app.task" "$file"; then
      echo "Moving $(basename "$file") to app/tasks/executions.py"
      cp "$file" "$BACKEND_DIR/app/tasks/executions.py"
    # Check if it contains schema indicators
    elif grep -q "class ExecutionBase" "$file" || grep -q "class ExecutionCreate" "$file"; then
      echo "Moving $(basename "$file") to app/schemas/execution.py"
      cp "$file" "$BACKEND_DIR/app/schemas/execution.py"
    else
      echo "Warning: Could not determine type of $(basename "$file")"
    fi
  fi
done

# Service files
if [ -f "$DOWNLOADS_DIR/executor.py" ]; then
  echo "Moving executor.py to app/services/executor.py"
  cp "$DOWNLOADS_DIR/executor.py" "$BACKEND_DIR/app/services/executor.py"
fi

if [ -f "$DOWNLOADS_DIR/scheduler.py" ]; then
  echo "Moving scheduler.py to app/services/scheduler.py"
  cp "$DOWNLOADS_DIR/scheduler.py" "$BACKEND_DIR/app/services/scheduler.py"
fi

# Task files
if [ -f "$DOWNLOADS_DIR/worker.py" ]; then
  echo "Moving worker.py to app/tasks/worker.py"
  cp "$DOWNLOADS_DIR/worker.py" "$BACKEND_DIR/app/tasks/worker.py"
fi

# Websocket files
if [ -f "$DOWNLOADS_DIR/manager.py" ]; then
  echo "Moving manager.py to app/websockets/manager.py"
  cp "$DOWNLOADS_DIR/manager.py" "$BACKEND_DIR/app/websockets/manager.py"
fi

if [ -f "$DOWNLOADS_DIR/routes.py" ]; then
  echo "Moving routes.py to app/websockets/routes.py"
  cp "$DOWNLOADS_DIR/routes.py" "$BACKEND_DIR/app/websockets/routes.py"
fi

# Environment file
if [ -f "$DOWNLOADS_DIR/.env" ]; then
  echo "Moving .env to root directory"
  cp "$DOWNLOADS_DIR/.env" "$BACKEND_DIR/.env"
fi

echo "File movement complete!"