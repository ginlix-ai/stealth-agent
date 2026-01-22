"""Pydantic models for Gmail API requests and responses."""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class SendEmailRequest(BaseModel):
    """Request model for sending an email."""

    from_email: EmailStr = Field(..., description="Sender email address")
    to_email: EmailStr = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject line", min_length=1)
    body: str = Field(..., description="Email body content", min_length=1)
    content_type: str = Field(
        default="text/plain",
        description="Content type: 'text/plain' or 'text/html'",
        pattern="^(text/plain|text/html)$",
    )
    attachment: Optional[str] = Field(
        None,
        description="Attachment file as base64-encoded string (required if attachment_filename provided)",
    )
    attachment_filename: Optional[str] = Field(
        None, description="Attachment filename (required if attachment provided)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "from_email": "user@gmail.com",
                "to_email": "recipient@example.com",
                "subject": "Hello from API",
                "body": "This is a test email sent from the Gmail API service.",
                "content_type": "text/plain",
            }
        }


class SendEmailResponse(BaseModel):
    """Response model for send email endpoint."""

    success: bool = Field(..., description="Whether email was sent successfully")
    message_id: str = Field(..., description="Gmail message ID")
    thread_id: Optional[str] = Field(None, description="Gmail thread ID")
    snippet: Optional[str] = Field(None, description="Email snippet/preview")
    message: str = Field(..., description="Status message")


class SendEmailErrorResponse(BaseModel):
    """Error response model."""

    success: bool = Field(False, description="Always false for errors")
    error: str = Field(..., description="Error message")
    details: Optional[str] = Field(None, description="Additional error details")

