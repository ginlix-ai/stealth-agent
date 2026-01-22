# Services Directory

This directory contains business logic services for the application. Services are separate from API routing logic and can be reused across different entry points (API, CLI, background jobs, etc.).

## Current Services

### GmailEmailService (`gmail_email_service.py`)

Email sending service using Gmail API. Handles:
- Sending emails with plain text or HTML content
- Attaching files to emails
- Token management and auto-refresh
- Error handling and validation

**Usage:**
```python
from services.gmail_email_service import GmailEmailService

service = GmailEmailService()

# Send simple email
result = service.send_email(
    from_email="your-email@gmail.com",
    to_email="recipient@example.com",
    subject="Hello",
    body="This is a test email"
)

# Send email with attachment
with open("file.pdf", "rb") as f:
    attachment_bytes = f.read()

result = service.send_email(
    from_email="your-email@gmail.com",
    to_email="recipient@example.com",
    subject="Email with attachment",
    body="Please find attached file.",
    attachment=attachment_bytes,
    attachment_filename="file.pdf"
)
```

## Adding New Services

When adding new services:

1. Create service file: `services/your_service_name_service.py`
2. Name the class descriptively: `YourServiceNameService`
3. Keep services focused on business logic (no routing)
4. Use dependency injection for configuration (credentials, tokens, etc.)
5. Handle errors appropriately and raise descriptive exceptions

### Example Service Structure

```python
"""Your Service Name Service

Description of what this service does.
"""

from typing import Any


class YourServiceNameService:
    """Service for [functionality description]."""
    
    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize service.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
    
    def your_method(self, param1: str, param2: int) -> dict[str, Any]:
        """Your method description.
        
        Args:
            param1: Description
            param2: Description
            
        Returns:
            Result dictionary
            
        Raises:
            ValueError: If parameters are invalid
        """
        # Your business logic here
        pass
```

## Architecture

```
project_root/
├── services/              # Business logic services (this directory)
│   ├── gmail_email_service.py
│   └── your_new_service.py
├── api/                   # API routing only
│   ├── main.py           # FastAPI routes
│   └── models/           # API request/response models
└── libs/                  # Core libraries (ptc-agent, ptc-cli)
```

**Separation of Concerns:**
- `services/` - Business logic, reusable across different entry points
- `api/` - HTTP routing, request/response handling, validation
- `libs/` - Core framework functionality

