# Workflow Automation API

A FastAPI backend for a workflow automation application that enables users to create, manage, and execute workflows with real-time logging capabilities.

## Features

- **Workflow Management**: Create, read, update, and delete workflow definitions
- **Workflow Execution**: Manual and scheduled execution of workflows
- **Real-time Logging**: WebSocket and Server-Sent Events (SSE) for real-time execution logs
- **Authentication**: JWT-based authentication using Auth0
- **Admin Capabilities**: Audit logging and system monitoring
- **Scheduling**: Support for cron-based workflow scheduling

## Technology Stack

- **FastAPI**: Modern, high-performance web framework for building APIs
- **SQLAlchemy**: ORM for database interactions
- **Pydantic**: Data validation and settings management
- **Celery**: Distributed task queue for background processing
- **Redis**: Message broker and results backend for Celery
- **WebSockets**: Real-time communication for log streaming
- **PostgreSQL**: Relational database

## Project Structure

The project follows a modular structure organized by feature:

```
workflow-automation-api/
├── app/
│   ├── api/              # API endpoints
│   ├── core/             # Core components
│   ├── db/               # Database configuration
│   ├── models/           # Database models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   ├── tasks/            # Background tasks
│   ├── utils/            # Utility functions
│   └── websockets/       # WebSocket handlers
└── tests/                # Test package
```

## Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL
- Redis

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/workflow-automation-api.git
   cd workflow-automation-api
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```
   cp .env.example .env
   # Edit .env file with your configuration
   ```

5. Initialize the database:
   ```
   alembic upgrade head
   ```

### Running the Application

Start the FastAPI application:
```
uvicorn app.main:app --reload
```

Start Celery worker:
```
celery -A app.tasks.worker.celery_app worker --loglevel=info
```

Start Celery beat for scheduled tasks:
```
celery -A app.tasks.worker.celery_app beat --loglevel=info
```

### API Documentation

Once the application is running, you can access the API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Authentication

This application uses Auth0 for authentication. To set up Auth0:

1. Create an Auth0 account and API
2. Configure the `.env` file with your Auth0 domain and audience
3. Set up appropriate permissions in Auth0

Required permissions:
- `create:workflows`
- `read:workflows`
- `update:workflows`
- `delete:workflows`
- `execute:workflows`
- `read:executions`
- `cancel:executions`
- `read:logs`

## Workflow Definition Format

Workflows are defined using a JSON schema. Here's a basic example:

```json
{
  "version": "1.0",
  "steps": [
    {
      "id": "step1",
      "name": "HTTP Request",
      "type": "http",
      "config": {
        "url": "https://api.example.com/data",
        "method": "GET"
      },
      "depends_on": []
    },
    {
      "id": "step2",
      "name": "Process Data",
      "type": "script",
      "config": {
        "language": "python",
        "code": "# Process data from step1\nresult = input['step1']['body']\noutput = {'processed': result}\n"
      },
      "depends_on": ["step1"]
    }
  ],
  "connections": [
    {
      "from": "step1",
      "to": "step2"
    }
  ],
  "variables": {
    "api_key": "{{ env.API_KEY }}"
  }
}
```

## Development

### Running Tests

```
pytest
```

### Code Style

This project uses Black for code formatting and isort for import sorting:

```
black app tests
isort app tests
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.