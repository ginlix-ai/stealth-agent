"""
Server script
"""

import argparse
import logging
import uvicorn

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run the server")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (default: True except on Windows)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host to bind the server to (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Log level (default: info)",
    )

    args = parser.parse_args()

    # Configure SSE event logger independently
    # This allows viewing ONLY SSE events by setting SSE_EVENT_LOG_LEVEL=info
    # and server --log-level=error
    import os
    sse_event_log_level = os.getenv("SSE_EVENT_LOG_LEVEL", "info").upper()
    sse_logger = logging.getLogger("sse_events")
    sse_logger.setLevel(getattr(logging, sse_event_log_level))
    # Ensure SSE logger outputs even when root logger level is higher
    sse_logger.propagate = True


    # Determine reload setting
    reload = False
    if args.reload:
        reload = True

    try:
        logger.info(f"Starting server on {args.host}:{args.port}")
        uvicorn.run(
            "src.server.app:app",
            host=args.host,
            port=args.port,
            reload=reload,
            log_level=args.log_level,
            timeout_keep_alive=300,  # 5 minutes - for long-running workflows
            timeout_graceful_shutdown=60,  # 60 seconds for graceful shutdown
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        exit(1)
