#!/bin/bash
# Script to find files by content and move them to the appropriate locations

# Set your downloads directory and backend directory
DOWNLOADS_DIR="/Users/markmcquade/Downloads"
BACKEND_DIR="backend"

# Make sure we're in the correct directory
if [ ! -d "$BACKEND_DIR" ]; then
  echo "Error: Backend directory not found. Please navigate to the parent directory of your backend folder."
  exit 1
fi

echo "Searching for files in $DOWNLOADS_DIR and moving them to $BACKEND_DIR structure..."

# Function to find a file by searching for a unique string in its content
find_file_by_content() {
  pattern="$1"
  dest_path="$2"
  
  # Find files containing the pattern
  for file in "$DOWNLOADS_DIR"/*.py; do
    if [ -f "$file" ] && grep -q "$pattern" "$file"; then
      echo "Found match for $dest_path in $(basename "$file")"
      cp "$file" "$BACKEND_DIR/$dest_path"
      return 0
    fi
  done
  
  echo "Warning: Could not find any file matching pattern for $dest_path"
  return 1
}

# Main app file
find_file_by_content "def create_application()" "app/main.py"

# Core module files
find_file_by_content "class Settings(BaseSettings)" "app/core/config.py"
find_file_by_content "class JWTBearer(HTTPBearer)" "app/core/auth.py"

# API module files
find_file_by_content "async def get_db()" "app/api/deps.py"
find_file_by_content "async def validation_exception_handler" "app/api/error_handlers.py"
find_file_by_content "api_router = APIRouter()" "app/api/v1/router.py"

# API endpoint files
find_file_by_content "async def create_workflow" "app/api/v1/endpoints/workflows.py"
find_file_by_content "async def start_execution" "app/api/v1/endpoints/executions.py"

# DB files
find_file_by_content "engine = create_async_engine" "app/db/session.py"
find_file_by_content "Base = declarative_base" "app/db/base.py"

# Model files
find_file_by_content "class Workflow(Base)" "app/models/workflow.py"
find_file_by_content "class AuditLog(Base)" "app/models/audit.py"

# Schema files
find_file_by_content "class WorkflowBase(BaseModel)" "app/schemas/workflow.py"
find_file_by_content "class ExecutionCreate(BaseModel)" "app/schemas/execution.py"

# Service files
find_file_by_content "async def execute_workflow" "app/services/executor.py"
find_file_by_content "async def create_schedule" "app/services/scheduler.py"
find_file_by_content "async def log_audit_event" "app/services/audit.py"

# Task files
find_file_by_content "def create_celery()" "app/tasks/worker.py"
find_file_by_content "run_workflow_execution_task" "app/tasks/executions.py"

# Websocket files
find_file_by_content "class ConnectionManager" "app/websockets/manager.py"
find_file_by_content "async def handle_execution_logs" "app/websockets/routes.py"

# Environment file (by name)
if [ -f "$DOWNLOADS_DIR/.env" ]; then
  echo "Moving .env to root directory"
  cp "$DOWNLOADS_DIR/.env" "$BACKEND_DIR/.env"
fi

echo "File search and movement complete!"