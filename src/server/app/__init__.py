"""
FastAPI application entry point with router registration.
"""

import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from src.server.app.setup import app

__all__ = ["app"]
