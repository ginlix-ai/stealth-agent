"""
Utility endpoints for TTS, podcast, RAG, config, health checks, and WebSocket.

This module handles miscellaneous endpoints:
- Text-to-speech conversion
- Podcast generation
- RAG configuration and resources
- Server configuration
- WebSocket chat
- Health checks
- Custom metrics
"""

import base64
import logging
import os
from datetime import datetime
from typing import Optional, List, Annotated

from fastapi import APIRouter, HTTPException, WebSocket, Request, Query
from fastapi.responses import Response

logger = logging.getLogger(__name__)
INTERNAL_SERVER_ERROR_DETAIL = "Internal Server Error"

# Create router (health checks are unversioned at /health)
health_router = APIRouter(tags=["Health"])

@health_router.get("/health")
async def health_check():
    """Health check endpoint with checkpointer pool stats."""
    from src.server.app.setup import checkpointer
    from src.server.utils.checkpointer import get_checkpointer_health

    result = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
        "service": "ptc-agent",
    }

    # Include checkpointer pool health if configured
    try:
        checkpointer_health = await get_checkpointer_health(checkpointer)
        result["checkpointer"] = checkpointer_health
        if checkpointer_health.get("status") == "unhealthy":
            result["status"] = "degraded"
    except Exception as e:
        result["checkpointer"] = {"status": "error", "error": str(e)}
        result["status"] = "degraded"

    return result