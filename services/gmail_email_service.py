"""
Gmail Email Sending Service

This service provides functionality to send emails via Gmail API with support for:
- Plain text and HTML emails
- Attachments (files)
- Custom from/to addresses
- Subject and body content

Located in services/ directory at project root (not in api/) to separate
business logic from routing/endpoints.
"""

import base64
import mimetypes
from pathlib import Path
from typing import Any

from email.message import EmailMessage
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GmailEmailService:
    """Service for sending emails via Gmail API.
    
    This service handles all Gmail API operations for sending emails.
    It is separate from API routing logic and can be reused across
    different entry points (API, CLI, background jobs, etc.).
    """

    # Required scopes for sending emails
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    ]

    def __init__(
        self,
        credentials_path: str | Path | None = None,
        token_path: str | Path | None = None,
    ):
        """Initialize Gmail Email service.

        Args:
            credentials_path: Path to credentials.json (default: project root/credentials.json)
            token_path: Path to token.json (default: project root/token.json)
        """
        # Default to project root (services/ is at root, so go up one level)
        project_root = Path(__file__).parent.parent

        self.credentials_path = (
            Path(credentials_path) if credentials_path else project_root / "credentials.json"
        )
        self.token_path = (
            Path(token_path) if token_path else project_root / "token.json"
        )
        self._service: Any | None = None

    def _get_credentials(self) -> Credentials:
        """Get authenticated credentials.

        Returns:
            Credentials object for Gmail API

        Raises:
            FileNotFoundError: If credentials.json or token.json not found
            ValueError: If credentials are invalid
        """
        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"credentials.json not found at {self.credentials_path}. "
                "Please run example/test_gmail_api.py first to authenticate."
            )

        if not self.token_path.exists():
            raise FileNotFoundError(
                f"token.json not found at {self.token_path}. "
                "Please run example/test_gmail_api.py first to authenticate."
            )

        creds = Credentials.from_authorized_user_file(str(self.token_path), self.SCOPES)

        # Refresh token if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed token
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        return creds

    def _get_service(self):
        """Get Gmail API service instance.

        Returns:
            Gmail service instance
        """
        if self._service is None:
            creds = self._get_credentials()
            self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def _create_message(
        self,
        from_email: str,
        to_email: str,
        subject: str,
        body_text: str,
        attachment: bytes | None = None,
        attachment_filename: str | None = None,
        content_type: str = "text/plain",
    ) -> dict[str, str]:
        """Create an email message ready to send via Gmail API.

        Uses EmailMessage API (Python 3.6+) as per Google's recommended approach.
        Body text appears directly in email body, not as attachment.

        Args:
            from_email: Sender email address
            to_email: Recipient email address
            subject: Email subject
            body_text: Email body content (plain text or HTML)
            attachment: Optional attachment file bytes
            attachment_filename: Optional attachment filename
            content_type: Content type for body (text/plain or text/html)

        Returns:
            Dictionary with 'raw' key containing base64-encoded message

        Raises:
            ValueError: If email addresses are invalid
        """
        # Create EmailMessage (modern API, as per Google samples)
        message = EmailMessage()

        # Set headers
        message["To"] = to_email
        message["From"] = from_email
        message["Subject"] = subject

        # Set body content - this appears directly in email body, not as attachment
        # The content_type parameter determines if it's plain text or HTML
        if content_type == "text/html":
            message.set_content(body_text, subtype="html")
        else:
            message.set_content(body_text)  # Defaults to text/plain

        # Add attachment if provided
        if attachment and attachment_filename:
            # Guess MIME type from filename
            type_subtype, _ = mimetypes.guess_type(attachment_filename)
            if type_subtype:
                maintype, subtype = type_subtype.split("/", 1)
            else:
                maintype = "application"
                subtype = "octet-stream"

            # Add attachment using EmailMessage's add_attachment method
            message.add_attachment(attachment, maintype=maintype, subtype=subtype, filename=attachment_filename)

        # Encode message as base64 URL-safe string (as per Google samples)
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        return {"raw": encoded_message}

    def send_email(
        self,
        from_email: str,
        to_email: str,
        subject: str,
        body: str,
        attachment: bytes | None = None,
        attachment_filename: str | None = None,
        content_type: str = "text/plain",
    ) -> dict[str, Any]:
        """Send an email via Gmail API.

        Args:
            from_email: Sender email address (must be authenticated user's email)
            to_email: Recipient email address
            subject: Email subject line
            body: Email body content
            attachment: Optional attachment file bytes
            attachment_filename: Optional attachment filename (required if attachment provided)
            content_type: Content type for body - "text/plain" or "text/html"

        Returns:
            Dictionary with message details including 'id' and 'threadId'

        Raises:
            FileNotFoundError: If credentials or token not found
            HttpError: If Gmail API request fails
            ValueError: If parameters are invalid

        Example:
            >>> service = GmailEmailService()
            >>> result = service.send_email(
            ...     from_email="user@gmail.com",
            ...     to_email="recipient@example.com",
            ...     subject="Hello",
            ...     body="This is a test email"
            ... )
            >>> print(f"Email sent! Message ID: {result['id']}")
        """
        # Validate inputs
        if not from_email or not to_email:
            raise ValueError("from_email and to_email are required")

        if not subject:
            raise ValueError("subject is required")

        if not body:
            raise ValueError("body is required")

        if attachment and not attachment_filename:
            raise ValueError(
                "attachment_filename is required when attachment is provided"
            )

        try:
            # Create message
            message = self._create_message(
                from_email=from_email,
                to_email=to_email,
                subject=subject,
                body_text=body,
                attachment=attachment,
                attachment_filename=attachment_filename,
                content_type=content_type,
            )

            # Send via Gmail API
            service = self._get_service()
            sent_message = service.users().messages().send(userId="me", body=message).execute()

            return {
                "id": sent_message["id"],
                "threadId": sent_message.get("threadId"),
                "labelIds": sent_message.get("labelIds", []),
                "snippet": sent_message.get("snippet", ""),
            }

        except HttpError as error:
            error_details = (
                error.error_details if hasattr(error, "error_details") else str(error)
            )
            raise ValueError(f"Gmail API error: {error_details}") from error
        except Exception as e:
            raise ValueError(f"Failed to send email: {str(e)}") from e

