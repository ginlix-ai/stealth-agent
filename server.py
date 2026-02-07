"""
Server script
"""

import sys
import os
import asyncio
import selectors

# Windows: 必须在任意 asyncio 使用前设置，否则 psycopg 会报 ProactorEventLoop 错误
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _selector_loop_factory():
    """Windows 下供 uvicorn 使用，创建 SelectorEventLoop 以兼容 psycopg。"""
    return asyncio.SelectorEventLoop(selectors.SelectSelector())

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
    # Add dedicated handler so SSE logs output independently of root logger level
    sse_handler = logging.StreamHandler()
    sse_handler.setLevel(getattr(logging, sse_event_log_level))
    sse_handler.setFormatter(logging.Formatter("%(message)s"))
    sse_logger.addHandler(sse_handler)
    # Prevent duplicate logs by not propagating to root logger
    sse_logger.propagate = False


    # Determine reload setting
    reload = False
    if args.reload:
        reload = True

    try:
        logger.info(f"Starting server on {args.host}:{args.port}")
        run_kwargs = {
            "app": "src.server.app:app",
            "host": args.host,
            "port": args.port,
            "reload": reload,
            "log_level": args.log_level,
            "timeout_keep_alive": 300,
            "timeout_graceful_shutdown": 60,
        }
        # Windows: uvicorn 默认用 ProactorEventLoop，与 psycopg 不兼容，传入 Selector 工厂（callable 避免模块导入问题）
        if sys.platform == "win32":
            run_kwargs["loop"] = _selector_loop_factory
        uvicorn.run(**run_kwargs)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        exit(1)
