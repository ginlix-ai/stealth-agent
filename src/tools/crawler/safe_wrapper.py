"""
Safe wrapper for Crawl4AI operations with isolation and fault tolerance.

Provides defense-in-depth protection:
- Circuit breaker for fault tolerance (fail fast after repeated failures)
- Timeouts for all operations (prevent hanging)
- Resource limiting (queue size, concurrency)
- Auto browser reset on circuit open
- Graceful degradation (never crash, always return structured errors)
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing fast, rejecting requests
    HALF_OPEN = "half_open" # Testing recovery


@dataclass
class CrawlResult:
    """Structured crawl result that never raises exceptions."""
    success: bool
    markdown: Optional[str] = None
    title: Optional[str] = None
    error: Optional[str] = None
    error_type: Optional[str] = None  # timeout, circuit_open, queue_full, browser_error, etc.


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class QueueFullError(Exception):
    """Raised when crawler queue is at capacity."""
    pass


class CrawlerCircuitBreaker:
    """
    Circuit breaker for crawler operations.

    State machine:
    - CLOSED: Normal operation, tracking failures
    - OPEN: After failure_threshold failures, reject all requests immediately
    - HALF_OPEN: After recovery_timeout, allow one request to test recovery

    When circuit opens, triggers browser reset to recover from corrupted state.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before transitioning from OPEN to HALF_OPEN
            success_threshold: Number of successes in HALF_OPEN to close circuit
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()

    async def check_state(self) -> None:
        """Check and potentially transition state based on time elapsed."""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self.last_failure_time and \
                   time.time() - self.last_failure_time > self.recovery_timeout:
                    logger.info("Circuit breaker transitioning to half-open")
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0

    async def record_success(self) -> None:
        """Record successful operation."""
        async with self._lock:
            self.failure_count = 0
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    logger.info("Circuit breaker closing after recovery")
                    self.state = CircuitState.CLOSED

    async def record_failure(self, trigger_reset: Optional[Callable] = None) -> None:
        """
        Record failed operation.

        Args:
            trigger_reset: Optional async callback to reset browser when circuit opens
        """
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            should_open = False

            if self.state == CircuitState.HALF_OPEN:
                logger.warning("Circuit breaker re-opening after half-open failure")
                self.state = CircuitState.OPEN
                should_open = True
            elif self.failure_count >= self.failure_threshold:
                logger.warning(f"Circuit breaker opening after {self.failure_count} failures")
                self.state = CircuitState.OPEN
                should_open = True

            # Trigger browser reset when circuit opens
            if should_open and trigger_reset:
                logger.info("Triggering browser reset due to circuit open")
                asyncio.create_task(trigger_reset())

    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        return self.state == CircuitState.OPEN


class SafeCrawlerWrapper:
    """
    Safe wrapper for Crawl4AI with comprehensive fault tolerance.

    Features:
    - Circuit breaker: Fail fast after repeated failures
    - Timeouts: All operations have guaranteed timeouts
    - Resource limiting: Queue size and concurrency limits
    - Auto recovery: Browser reset when circuit opens
    - Graceful degradation: Never raises, always returns CrawlResult
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        max_queue_size: int = 100,
        default_timeout: float = 60.0,
        slot_timeout: float = 10.0,
        circuit_failure_threshold: int = 5,
        circuit_recovery_timeout: float = 60.0,
        circuit_success_threshold: int = 2,
    ):
        """
        Initialize safe crawler wrapper.

        Args:
            max_concurrent: Maximum number of concurrent crawls
            max_queue_size: Maximum number of queued requests
            default_timeout: Default timeout for crawl operations (seconds)
            slot_timeout: Timeout for waiting for a crawl slot (seconds)
            circuit_failure_threshold: Failures before opening circuit
            circuit_recovery_timeout: Seconds before testing recovery
            circuit_success_threshold: Successes to close circuit
        """
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue_count = 0
        self._max_queue = max_queue_size
        self._default_timeout = default_timeout
        self._slot_timeout = slot_timeout
        self._circuit = CrawlerCircuitBreaker(
            failure_threshold=circuit_failure_threshold,
            recovery_timeout=circuit_recovery_timeout,
            success_threshold=circuit_success_threshold,
        )
        self._lock = asyncio.Lock()
        self._crawler = None  # Lazy-initialized

    async def _get_crawler(self):
        """Lazy-initialize crawler."""
        if self._crawler is None:
            from .crawl4ai_crawler import Crawl4AICrawler
            self._crawler = Crawl4AICrawler()
        return self._crawler

    async def _trigger_browser_reset(self) -> None:
        """Reset browser when circuit opens to recover from corrupted state."""
        try:
            from .crawl4ai_client import Crawl4AIBrowserManager
            manager = await Crawl4AIBrowserManager.get_instance()
            await manager._reset_browser()
            logger.info("Browser reset completed after circuit open")
        except Exception as e:
            logger.error(f"Browser reset failed: {e}")

    async def crawl(
        self,
        url: str,
        timeout: Optional[float] = None,
    ) -> CrawlResult:
        """
        Safely crawl a URL with all protections.

        This method never raises exceptions - it always returns a CrawlResult
        with success=True/False and appropriate error information.

        Args:
            url: URL to crawl
            timeout: Optional timeout override (seconds)

        Returns:
            CrawlResult with success status and content/error
        """
        timeout = timeout or self._default_timeout

        # Check circuit breaker state
        await self._circuit.check_state()
        if self._circuit.is_open():
            return CrawlResult(
                success=False,
                error="Crawler temporarily unavailable (circuit open)",
                error_type="circuit_open",
            )

        # Check queue capacity
        async with self._lock:
            if self._queue_count >= self._max_queue:
                return CrawlResult(
                    success=False,
                    error="Crawler queue at capacity",
                    error_type="queue_full",
                )
            self._queue_count += 1

        try:
            # Acquire semaphore with timeout
            try:
                await asyncio.wait_for(
                    self._semaphore.acquire(),
                    timeout=self._slot_timeout,
                )
            except asyncio.TimeoutError:
                return CrawlResult(
                    success=False,
                    error=f"Timeout waiting for crawler slot ({self._slot_timeout}s)",
                    error_type="queue_timeout",
                )

            try:
                # Execute crawl with timeout
                crawler = await self._get_crawler()
                markdown = await asyncio.wait_for(
                    crawler.crawl(url),
                    timeout=timeout,
                )

                await self._circuit.record_success()
                return CrawlResult(
                    success=True,
                    markdown=markdown,
                )

            except asyncio.TimeoutError:
                await self._circuit.record_failure(self._trigger_browser_reset)
                return CrawlResult(
                    success=False,
                    error=f"Crawl timed out after {timeout}s",
                    error_type="timeout",
                )
            except asyncio.CancelledError:
                # Don't count cancellation as failure
                return CrawlResult(
                    success=False,
                    error="Crawl was cancelled",
                    error_type="cancelled",
                )
            except Exception as e:
                await self._circuit.record_failure(self._trigger_browser_reset)
                error_str = str(e)

                # Classify error type for better diagnostics
                if "has been closed" in error_str or "Target page" in error_str:
                    error_type = "browser_closed"
                elif "ERR_NAME_NOT_RESOLVED" in error_str:
                    error_type = "dns_error"
                elif "ERR_CONNECTION_REFUSED" in error_str:
                    error_type = "connection_refused"
                elif "ERR_CONNECTION_TIMED_OUT" in error_str:
                    error_type = "connection_timeout"
                elif "net::" in error_str:
                    error_type = "network_error"
                else:
                    error_type = "crawl_error"

                return CrawlResult(
                    success=False,
                    error=error_str[:200],  # Truncate long errors
                    error_type=error_type,
                )
            finally:
                self._semaphore.release()
        finally:
            async with self._lock:
                self._queue_count -= 1

    def get_status(self) -> dict:
        """
        Get wrapper status for monitoring.

        Returns:
            Dict with circuit state, failure count, queue info
        """
        return {
            "circuit_state": self._circuit.state.value,
            "failure_count": self._circuit.failure_count,
            "success_count": self._circuit.success_count,
            "queue_count": self._queue_count,
            "max_queue": self._max_queue,
            "last_failure_time": self._circuit.last_failure_time,
        }

    def is_healthy(self) -> bool:
        """Check if crawler is healthy (circuit not open)."""
        return not self._circuit.is_open()


# Global singleton instance
_safe_wrapper: Optional[SafeCrawlerWrapper] = None
_wrapper_lock = asyncio.Lock()


async def get_safe_crawler() -> SafeCrawlerWrapper:
    """
    Get or create safe crawler wrapper singleton.

    Loads configuration from conf.yaml if available.
    """
    global _safe_wrapper

    if _safe_wrapper is not None:
        return _safe_wrapper

    async with _wrapper_lock:
        # Double-check after acquiring lock
        if _safe_wrapper is not None:
            return _safe_wrapper

        # Load config
        try:
            from src.config.loader import load_yaml_config
            config = load_yaml_config("conf.yaml")
            crawler_config = config.get("crawler", {})
            circuit_config = crawler_config.get("circuit_breaker", {})
            queue_config = crawler_config.get("queue", {})

            _safe_wrapper = SafeCrawlerWrapper(
                max_concurrent=crawler_config.get("max_concurrent_crawls", 10),
                default_timeout=crawler_config.get("page_timeout", 60000) / 1000,
                max_queue_size=queue_config.get("max_size", 100),
                slot_timeout=queue_config.get("slot_timeout", 10),
                circuit_failure_threshold=circuit_config.get("failure_threshold", 5),
                circuit_recovery_timeout=circuit_config.get("recovery_timeout", 60),
                circuit_success_threshold=circuit_config.get("success_threshold", 2),
            )
        except Exception as e:
            logger.warning(f"Failed to load crawler config, using defaults: {e}")
            _safe_wrapper = SafeCrawlerWrapper()

        return _safe_wrapper


def get_safe_crawler_sync() -> SafeCrawlerWrapper:
    """
    Synchronous version of get_safe_crawler for non-async contexts.

    Note: This creates the wrapper with default config if not already initialized.
    """
    global _safe_wrapper

    if _safe_wrapper is None:
        # Load config synchronously
        try:
            from src.config.loader import load_yaml_config
            config = load_yaml_config("conf.yaml")
            crawler_config = config.get("crawler", {})
            circuit_config = crawler_config.get("circuit_breaker", {})
            queue_config = crawler_config.get("queue", {})

            _safe_wrapper = SafeCrawlerWrapper(
                max_concurrent=crawler_config.get("max_concurrent_crawls", 10),
                default_timeout=crawler_config.get("page_timeout", 60000) / 1000,
                max_queue_size=queue_config.get("max_size", 100),
                slot_timeout=queue_config.get("slot_timeout", 10),
                circuit_failure_threshold=circuit_config.get("failure_threshold", 5),
                circuit_recovery_timeout=circuit_config.get("recovery_timeout", 60),
                circuit_success_threshold=circuit_config.get("success_threshold", 2),
            )
        except Exception as e:
            logger.warning(f"Failed to load crawler config, using defaults: {e}")
            _safe_wrapper = SafeCrawlerWrapper()

    return _safe_wrapper
