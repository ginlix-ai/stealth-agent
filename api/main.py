"""
FastAPI REST API Server for Open PTC Agent

This module provides REST API endpoints for interacting with the PTC Agent backend.
The API is designed to be consumed by frontend applications (React, etc.).

Usage:
    uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload

Or use the run script:
    python -m api.main
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from api.models.gmail import SendEmailRequest, SendEmailResponse, SendEmailErrorResponse
from api.models.agent import AgentChatRequest, AgentChatResponse
from services.gmail_email_service import GmailEmailService
from services.agent_service import AgentService

# Create FastAPI app instance
app = FastAPI(
    title="Open PTC Agent API",
    description="REST API for Open PTC Agent - Programmatic Tool Calling with MCP",
    version="0.1.0",
)

# Configure CORS to allow frontend connections
# In production, replace "*" with your React app's domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins - update for production
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)


@app.get("/")
async def root():
    """Root endpoint - API health check."""
    return {
        "message": "Open PTC Agent API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/hello")
async def hello():
    """
    Simple hello endpoint for testing.
    
    Returns:
        str: "Hello!" message
    """
    return "Hello, this is a message from the API!"


# Health check endpoint
@app.get("/health")
async def health():
    """Health check endpoint for monitoring."""
    return {"status": "healthy"}


# Gmail Email Sending Endpoints
@app.post("/api/v1/gmail/send", response_model=SendEmailResponse)
async def send_email(request: SendEmailRequest):
    """
    Send an email via Gmail API.
    
    Supports:
    - Plain text and HTML emails
    - Optional attachments (via base64 encoding in JSON)
    
    Args:
        request: SendEmailRequest with email parameters
        
    Returns:
        SendEmailResponse with message ID and details
        
    Example JSON request:
    ```json
    {
        "from_email": "your-email@gmail.com",
        "to_email": "recipient@example.com",
        "subject": "Hello from API",
        "body": "This is a test email",
        "content_type": "text/plain",
        "attachment": null,
        "attachment_filename": null
    }
    ```
    """
    try:
        # Decode base64 attachment if provided
        attachment_bytes = None
        if request.attachment:
            import base64
            try:
                # Attachment comes as base64 string from JSON
                attachment_bytes = base64.b64decode(request.attachment)
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid base64 attachment format: {str(e)}. Attachment must be base64-encoded string."
                )
        
        # Validate attachment filename if attachment provided
        if attachment_bytes and not request.attachment_filename:
            raise HTTPException(
                status_code=400,
                detail="attachment_filename is required when attachment is provided"
            )
        
        # Create Gmail Email service and send email
        service = GmailEmailService()
        result = service.send_email(
            from_email=request.from_email,
            to_email=request.to_email,
            subject=request.subject,
            body=request.body,
            attachment=attachment_bytes,
            attachment_filename=request.attachment_filename,
            content_type=request.content_type,
        )
        
        return SendEmailResponse(
            success=True,
            message_id=result["id"],
            thread_id=result.get("threadId"),
            snippet=result.get("snippet"),
            message=f"Email sent successfully! Message ID: {result['id']}"
        )
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Authentication required: {str(e)}. Please run example/test_gmail_api.py first."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send email: {str(e)}"
        )


@app.post("/api/v1/gmail/send-with-file", response_model=SendEmailResponse)
async def send_email_with_file(
    from_email: str = Form(..., description="Sender email address"),
    to_email: str = Form(..., description="Recipient email address"),
    subject: str = Form(..., description="Email subject"),
    body: str = Form(..., description="Email body content"),
    content_type: str = Form(default="text/plain", description="Content type: text/plain or text/html"),
    attachment: Optional[UploadFile] = File(None, description="Attachment file (optional)"),
):
    """
    Send an email with file attachment via multipart/form-data.
    
    This endpoint accepts file uploads via multipart/form-data, which is easier
    for Postman/file uploads but requires form encoding.
    
    Args:
        from_email: Sender email address
        to_email: Recipient email address
        subject: Email subject
        body: Email body content
        content_type: Content type (text/plain or text/html)
        attachment: Optional file attachment
        
    Returns:
        SendEmailResponse with message ID and details
        
    Example curl:
    ```bash
    curl -X POST http://localhost:8080/api/v1/gmail/send-with-file \
      -F "from_email=your-email@gmail.com" \
      -F "to_email=recipient@example.com" \
      -F "subject=Hello" \
      -F "body=Test email with attachment" \
      -F "attachment=@/path/to/file.pdf"
    ```
    """
    try:
        # Read attachment if provided
        attachment_bytes = None
        attachment_filename = None
        
        if attachment:
            attachment_bytes = await attachment.read()
            attachment_filename = attachment.filename or "attachment"
        
        # Create Gmail Email service and send email
        service = GmailEmailService()
        result = service.send_email(
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            body=body,
            attachment=attachment_bytes,
            attachment_filename=attachment_filename,
            content_type=content_type,
        )
        
        return SendEmailResponse(
            success=True,
            message_id=result["id"],
            thread_id=result.get("threadId"),
            snippet=result.get("snippet"),
            message=f"Email sent successfully! Message ID: {result['id']}"
        )
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Authentication required: {str(e)}. Please run example/test_gmail_api.py first."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send email: {str(e)}"
        )


# Agent Chat Endpoint
@app.post("/api/v1/agent/chat", response_model=AgentChatResponse)
async def agent_chat(request: AgentChatRequest):
    """
    Send a message to the PTC Agent and get a response.
    
    This endpoint:
    - Accepts user input as a string
    - Sends it to the agent server (same as CLI)
    - Accumulates the response from SSE stream
    - Returns the complete response
    
    Args:
        request: AgentChatRequest with message and optional parameters
        
    Returns:
        AgentChatResponse with agent's response message and metadata
        
    Example JSON request:
    ```json
    {
        "message": "Hello, can you help me analyze this code?",
        "workspace_id": null,
        "thread_id": null,
        "plan_mode": false
    }
    ```
    """
    try:
        # Create agent service
        service = AgentService()
        
        # Send message to agent
        result = await service.chat(
            message=request.message,
            workspace_id=request.workspace_id,
            thread_id=request.thread_id,
            plan_mode=request.plan_mode,
        )
        
        # Return response
        return AgentChatResponse(
            success=result["success"],
            message=result["message"],
            thread_id=result["thread_id"],
            workspace_id=result["workspace_id"],
            tool_calls=result["tool_calls"],
            error=result["error"],
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process agent request: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    
    # Run the server
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,  # Auto-reload on code changes (development only)
    )

