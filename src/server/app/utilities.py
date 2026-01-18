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
    """health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
        "service": "ptc-agent"
    }