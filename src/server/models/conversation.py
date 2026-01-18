"""
Pydantic models for conversation management API.

This module defines response models for conversation endpoints that work with
the query-response schema (conversation_history, thread, query, response).
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ==================== Conversation Response Models ====================

class ConversationListItem(BaseModel):
    """Response model for a conversation in list view."""
    conversation_id: str = Field(..., description="Conversation ID")
    user_id: str = Field(..., description="User ID")
    title: Optional[str] = Field(None, description="Conversation title")
    thread_count: int = Field(0, description="Number of threads in conversation")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "3d4e5f6g-7h8i-9j0k-1l2m-3n4o5p6q7r8s",
                "user_id": "user123",
                "title": "US Market Analysis",
                "thread_count": 3,
                "created_at": "2025-10-15T10:30:00Z",
                "updated_at": "2025-10-15T14:45:00Z"
            }
        }


class ConversationsListResponse(BaseModel):
    """Response model for listing conversations."""
    conversations: List[ConversationListItem] = Field(
        default_factory=list, description="List of conversations"
    )
    total: int = Field(0, description="Total number of conversations")
    limit: int = Field(..., description="Page limit")
    offset: int = Field(..., description="Page offset")


# ==================== Debug Response Models ====================

class ResponseFullDetail(BaseModel):
    """Complete response details including state_snapshot and agent_messages."""
    response_id: str = Field(..., description="Response ID")
    thread_id: str = Field(..., description="Thread ID")
    pair_index: int = Field(..., description="Pair index")
    status: str = Field(..., description="Response status")
    interrupt_reason: Optional[str] = Field(None, description="Interrupt reason")
    final_output: Optional[Dict[str, Any]] = Field(None, description="Final output")
    state_snapshot: Optional[Dict[str, Any]] = Field(None, description="Complete LangGraph state snapshot")
    agent_messages: Optional[Dict[str, Any]] = Field(None, description="Agent messages by agent name")
    token_usage: Optional[Dict[str, Any]] = Field(None, description="Token usage details")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    execution_time: float = Field(0.0, description="Execution time in seconds")
    timestamp: datetime = Field(..., description="Response timestamp")


# ==================== Messages API Response Models ====================

class MessageQuery(BaseModel):
    """Query information for messages endpoint."""
    query_id: str = Field(..., description="Query ID")
    content: str = Field(..., description="Query content")
    type: str = Field(..., description="Query type (initial, resume_feedback)")
    feedback_action: Optional[str] = Field(None, description="Feedback action if applicable")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Query metadata")
    timestamp: datetime = Field(..., description="Query timestamp")


class FileSnapshot(BaseModel):
    """File state snapshot at thread start."""
    file_id: str = Field(..., description="File ID")
    content: str = Field(..., description="File contents")
    line_count: int = Field(..., description="Number of lines in file")
    updated_in_thread_id: str = Field(..., description="Thread that last modified this file")
    updated_in_pair_index: int = Field(..., description="Pair index when last modified")

    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "file-uuid-1",
                "content": "# Tesla Analysis...",
                "line_count": 250,
                "updated_in_thread_id": "thread-1-uuid",
                "updated_in_pair_index": 0
            }
        }


class FileOperationEvent(BaseModel):
    """File operation event (SSE-compatible format)."""
    operation: str = Field(..., description="Operation type: write_file, edit_file, delete")
    file_path: str = Field(..., description="Full file path (e.g., /report/tesla.md)")
    content: Optional[str] = Field(None, description="File contents (write_file only, null for edit_file)")
    line_count: int = Field(..., description="Number of lines in file")
    agent: str = Field(..., description="Agent that performed operation")
    thread_id: str = Field(..., description="Thread where operation occurred")
    pair_index: int = Field(..., description="Query-response pair index")
    timestamp: datetime = Field(..., description="Operation timestamp")
    operation_index: int = Field(..., description="Sequential operation index per file (0, 1, 2, ...)")

    # For edit operations
    old_string: Optional[str] = Field(None, description="For edit_file: string being replaced")
    new_string: Optional[str] = Field(None, description="For edit_file: replacement string")

    # Metadata
    tool_call_id: Optional[str] = Field(None, description="LangChain tool call ID")
    file_id: str = Field(..., description="File ID for tracking")

    class Config:
        json_schema_extra = {
            "example": {
                "operation": "write_file",
                "file_path": "/report/tesla.md",
                "content": "# Tesla Analysis...",
                "line_count": 250,
                "agent": "coder",
                "thread_id": "thread-1-uuid",
                "pair_index": 0,
                "timestamp": "2025-01-15T10:30:00Z",
                "old_string": None,
                "new_string": None,
                "tool_call_id": "call_abc123",
                "file_id": "file-uuid-1"
            }
        }


class MessageResponse(BaseModel):
    """Response information for messages endpoint (excludes token_usage and state_snapshot)."""
    response_id: str = Field(..., description="Response ID")
    status: str = Field(..., description="Response status (completed, interrupted, error, timeout)")
    interrupt_reason: Optional[str] = Field(None, description="Interrupt reason if applicable")
    final_output: Optional[Dict[str, Any]] = Field(None, description="Final output (text, reasoning)")
    agent_messages: Optional[Dict[str, Any]] = Field(None, description="Agent messages for activity panel")
    execution_time: float = Field(0.0, description="Execution time in seconds")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    timestamp: datetime = Field(..., description="Response timestamp")

    # Filesystem: Snapshot + delta model
    file_snapshot: Optional[Dict[str, FileSnapshot]] = Field(
        None,
        description="File state at thread start (before this thread's operations)"
    )
    file_operations: Optional[List[FileOperationEvent]] = Field(
        None,
        description="New file operations performed in this thread"
    )


class ConversationMessage(BaseModel):
    """A single message pair in a conversation (query + response)."""
    pair_index: int = Field(..., description="Pair index within thread (0-based)")
    thread_id: str = Field(..., description="Thread ID (internal reference)")
    thread_index: int = Field(..., description="Thread index within conversation (0-based)")
    query: MessageQuery = Field(..., description="Query details")
    response: Optional[MessageResponse] = Field(None, description="Response details (may be null if pending)")


class ConversationMessagesResponse(BaseModel):
    """Response model for getting all messages in a conversation."""
    conversation_id: str = Field(..., description="Conversation ID")
    user_id: str = Field(..., description="User ID")
    title: Optional[str] = Field(None, description="Conversation title")
    messages: List[ConversationMessage] = Field(default_factory=list, description="All messages chronologically")
    total_messages: int = Field(0, description="Total message count")
    has_more: bool = Field(False, description="Whether more messages are available")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "conv-abc",
                "user_id": "user123",
                "title": "AMD Stock Analysis",
                "messages": [
                    {
                        "pair_index": 0,
                        "thread_id": "thread-1",
                        "thread_index": 0,
                        "query": {
                            "query_id": "query-1",
                            "content": "Analyze AMD stock",
                            "type": "initial",
                            "timestamp": "2025-10-15T21:03:43Z"
                        },
                        "response": {
                            "response_id": "resp-1",
                            "status": "completed",
                            "final_output": {"text": "# AMD Analysis..."},
                            "agent_messages": {"planner": [], "researcher": []},
                            "execution_time": 123.45,
                            "timestamp": "2025-10-15T21:05:47Z"
                        }
                    }
                ],
                "total_messages": 1,
                "has_more": False,
                "created_at": "2025-10-15T21:03:43Z",
                "updated_at": "2025-10-15T21:05:47Z"
            }
        }
