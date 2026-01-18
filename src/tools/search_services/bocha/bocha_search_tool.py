"""
LangChain-compatible Bocha Search Tool.

This module provides a LangChain tool wrapper around the BochaAPI
for integration with the search service backend.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Tuple, Union, List, Literal
from datetime import datetime

from langchain_core.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from src.tools.search_services.bocha import BochaAPI

logger = logging.getLogger(__name__)


class BochaSearchInput(BaseModel):
    """Input schema for Bocha search tool with time filtering support.

    Bocha search is optimized for Chinese language queries and Chinese market content.
    Supports time-based filtering similar to Tavily search.
    """

    query: str = Field(description="Search query to look up (supports Chinese and English)")

    time_range: Optional[Literal["day", "week", "month", "year", "d", "w", "m", "y"]] = Field(
        default=None,
        description=(
            "Filter results by relative time from now. "
            "'day'/'d' = past 24 hours, 'week'/'w' = past week, "
            "'month'/'m' = past month, 'year'/'y' = past year. "
            "If start_date or end_date is provided, this parameter is ignored."
        )
    )

    start_date: Optional[str] = Field(
        default=None,
        description=(
            "Start date for filtering results (YYYY-MM-DD format). "
            "Returns results from this date onwards. "
            "If provided with end_date, searches within date range. "
            "If provided alone, searches from this date to present."
        )
    )

    end_date: Optional[str] = Field(
        default=None,
        description=(
            "End date for filtering results (YYYY-MM-DD format). "
            "Returns results up to this date. "
            "Should be used with start_date for date range searches."
        )
    )

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate date format is YYYY-MM-DD and represents a valid date."""
        if v is None:
            return v

        # Check format
        if not v or len(v) != 10:
            raise ValueError("Date must be in YYYY-MM-DD format (e.g., '2025-01-15')")

        parts = v.split('-')
        if len(parts) != 3:
            raise ValueError("Date must be in YYYY-MM-DD format (e.g., '2025-01-15')")

        try:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format with valid integers")

        # Validate it's a real date
        try:
            datetime(year, month, day)
        except ValueError as e:
            raise ValueError(f"Invalid date: {e}")

        return v


class BochaSearchTool(BaseTool):
    """
    LangChain-compatible tool for Bocha web search.

    Bocha (豆包) is a Chinese search API service optimized for Chinese language queries
    and Chinese market content.

    Returns search results in two formats:
    1. Cleaned results for LLM consumption (list of dicts)
    2. Raw API response for debugging/logging

    Example:
        >>> tool = BochaSearchTool(max_results=5)
        >>> results, raw = tool.invoke({"query": "白酒股票分析"})
    """

    name: str = "web_search"
    description: str = (
        "使用豆包(Bocha)搜索引擎进行网页搜索。"
        "适用于中文查询和中国市场内容搜索。"
        "支持时间范围过滤（time_range, start_date, end_date）。"
        "A web search engine optimized for Chinese language queries. "
        "Useful for finding Chinese market information, news, and general web content. "
        "Supports time-based filtering (time_range for relative time, start_date/end_date for specific ranges)."
    )

    args_schema: type[BaseModel] = BochaSearchInput
    response_format: str = "content_and_artifact"  # Enable artifact support
    api_wrapper: BochaAPI = Field(default_factory=BochaAPI)
    max_results: int = Field(default=10, description="Maximum number of search results to return")

    verbose: bool = True
    """Control verbosity of search results at initialization time.

    - True (default): Include images in results
    - False: Exclude images, return webpage results only (lightweight for planning)

    This parameter is set at tool initialization, not controlled by LLM at query time.
    """

    default_time_range: Optional[str] = None
    """Default time range to use if LLM doesn't specify one.

    Set at initialization to provide a default time filter:
    - None (default): No default, LLM decides dynamically
    - "d"/"day": Default to past 24 hours
    - "w"/"week": Default to past 7 days
    - "m"/"month": Default to past 30 days
    - "y"/"year": Default to past 365 days

    LLM can still override by specifying a different time_range in query.
    """

    def _translate_time_to_freshness(
        self,
        time_range: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str]
    ) -> Optional[str]:
        """
        Translate Tavily-style time parameters to Bocha's freshness format.

        Priority: Date range (start_date/end_date) > time_range > None (noLimit)

        Args:
            time_range: Relative time filter (day/week/month/year or d/w/m/y)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Bocha freshness parameter value or None for no filtering
        """
        # Priority 1: Explicit date range
        if start_date or end_date:
            if start_date and end_date:
                # Date range: "YYYY-MM-DD..YYYY-MM-DD"
                return f"{start_date}..{end_date}"
            elif start_date:
                # From specific date to present: just use the date
                # Note: Bocha doesn't have "from date onwards" - we use the date itself
                return start_date
            else:
                # end_date only - not typically meaningful for search, but support it
                logger.warning(f"end_date provided without start_date: {end_date}. Using as specific date.")
                return end_date

        # Priority 2: Relative time range
        if time_range:
            # Map Tavily-style time_range to Bocha freshness values
            time_range_map = {
                "day": "oneDay",
                "d": "oneDay",
                "week": "oneWeek",
                "w": "oneWeek",
                "month": "oneMonth",
                "m": "oneMonth",
                "year": "oneYear",
                "y": "oneYear",
            }

            if time_range in time_range_map:
                return time_range_map[time_range]
            else:
                logger.warning(f"Unknown time_range value: {time_range}. Using noLimit.")
                return "noLimit"

        # Priority 3: No time filtering (default)
        return "noLimit"

    def _filter_artifact_for_frontend(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter artifact to remove content duplication for frontend display.

        Removes: content, summary, snippet, site_name from results
        Keeps: query, response_time, total_results, results[].{title, url, favicon, publish_time, id, snippet}, images

        Args:
            raw_data: Full raw data with all fields

        Returns:
            Filtered artifact with UI-only metadata
        """
        filtered = {
            "query": raw_data.get("query", ""),
            "response_time": raw_data.get("response_time", 0),
            "total_results": raw_data.get("total_results", 0),
            "results": [],
            "images": []
        }

        # Filter webpage results - keep UI metadata only
        for result in raw_data.get("results", []):
            if result.get("type") == "webpage":
                filtered["results"].append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "favicon": result.get("favicon", ""),
                    "publish_time": result.get("publish_time", ""),
                    "id": result.get("id", ""),
                    "snippet": result.get("snippet", "")  # Brief excerpt for UI preview
                    # NO content, summary, site_name (avoid duplication)
                })

        # Filter image results - only include when verbose=True
        if self.verbose:
            for result in raw_data.get("results", []):
                if result.get("type") == "image":
                    filtered["images"].append({
                        "image_url": result.get("image_url", ""),
                        "thumbnail_url": result.get("thumbnail_url", ""),
                        "source_url": result.get("source_url", "")
                    })

        # Add conversation metadata if available
        if "conversation_id" in raw_data:
            filtered["conversation_id"] = raw_data["conversation_id"]
        if "log_id" in raw_data:
            filtered["log_id"] = raw_data["log_id"]

        return filtered

    def _run(
        self,
        query: str,
        time_range: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        topic: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Tuple[Union[List[Dict[str, Any]], str], Dict[str, Any]]:
        """
        Execute Bocha search synchronously by running async code.

        Args:
            query: Search query string
            time_range: Relative time filter (day/week/month/year or d/w/m/y)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            topic: Search topic (general/news/finance). Accepted for compatibility but not used by Bocha API.
            run_manager: Optional callback manager (unused)

        Returns:
            Tuple of (cleaned_results, raw_response)
            - cleaned_results: List of dicts with title, url, summary, publish_time
            - raw_response: Dict with LLM-formatted string and preview list
        """
        logger.debug(f"Bocha search called in sync mode for query: {query[:50]}...")
        # BochaAPI is async-only, so we run the async method using asyncio.run()
        return asyncio.run(self._arun(query, time_range, start_date, end_date, topic, run_manager))

    async def _arun(
        self,
        query: str,
        time_range: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        topic: Optional[str] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> Tuple[Union[List[Dict[str, Any]], str], Dict[str, Any]]:
        """
        Execute Bocha AI search asynchronously with artifact support.

        Args:
            query: Search query string
            time_range: Relative time filter (day/week/month/year or d/w/m/y)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            topic: Search topic (general/news/finance). Accepted for compatibility but not used by Bocha API.
            run_manager: Optional callback manager

        Returns:
            Tuple of (content, artifact):
            - content: List for LLM consumption (webpages + images)
            - artifact: Dict for UI display (metadata only)
        """
        try:
            # Log topic parameter if provided (Bocha doesn't support topic filtering)
            if topic and topic != "general":
                logger.debug(
                    f"Topic parameter '{topic}' provided but ignored (Bocha API does not support topic-based filtering)"
                )

            # Apply default time_range if LLM didn't specify one
            effective_time_range = time_range or self.default_time_range
            if effective_time_range != time_range:
                logger.debug(
                    f"Using default time_range: {effective_time_range} "
                    f"(LLM: {time_range}, default: {self.default_time_range})"
                )

            # Translate time parameters to Bocha's freshness format
            freshness = self._translate_time_to_freshness(effective_time_range, start_date, end_date)

            # Execute search via BochaAPI (now returns results_list, metadata)
            api_results, metadata = await self.api_wrapper.web_search(
                query=query,
                count=self.max_results,
                freshness=freshness,
                answer=False  # Don't request LLM answer
            )

            # Build content for LLM (focused, no UI metadata)
            content: List[Dict[str, Any]] = []

            for item in api_results:
                if item.get("type") == "webpage":
                    content.append({
                        "type": "page",
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "content": item.get("summary", ""),  # Primary content for LLM
                        "publish_time": item.get("publish_time", ""),
                        "site_name": item.get("site_name", "")  # Source credibility
                    })
                elif item.get("type") == "image" and self.verbose:
                    # Only include images when verbose=True
                    content.append({
                        "type": "image",
                        "image_url": item.get("content_url", ""),
                        "image_description": ""  # Bocha doesn't provide descriptions
                    })

            # Build raw data structure with all fields (for artifact filtering)
            raw_data = {
                "query": metadata.get("query", query),
                "response_time": metadata.get("response_time", 0),
                "total_results": metadata.get("total_results", 0),
                "results": []
            }

            # Add all fields to raw data
            for item in api_results:
                if item.get("type") == "webpage":
                    raw_data["results"].append({
                        "type": "webpage",
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "favicon": item.get("site_icon", ""),  # Map site_icon to favicon
                        "publish_time": item.get("publish_time", ""),
                        "id": item.get("id", ""),
                        "snippet": item.get("snippet", ""),
                        # Include content fields for filtering (will be removed)
                        "content": item.get("summary", ""),
                        "summary": item.get("summary", ""),
                        "site_name": item.get("site_name", "")
                    })
                elif item.get("type") == "image":
                    raw_data["results"].append({
                        "type": "image",
                        "image_url": item.get("content_url", ""),
                        "thumbnail_url": item.get("thumbnail_url", ""),
                        "source_url": item.get("host_page_url", "")
                    })

            # Add conversation metadata
            if "conversation_id" in metadata:
                raw_data["conversation_id"] = metadata["conversation_id"]
            if "log_id" in metadata:
                raw_data["log_id"] = metadata["log_id"]

            # Filter artifact to remove content duplication
            artifact = self._filter_artifact_for_frontend(raw_data)

            logger.info(f"Bocha AI search completed: {len(content)} items for query '{query[:50]}...'")
            logger.debug(f"Content structure: {len([c for c in content if c.get('type')=='page'])} pages, "
                        f"{len([c for c in content if c.get('type')=='image'])} images")

            return content, artifact

        except Exception as e:
            logger.error(f"Bocha AI search failed: {e}", exc_info=True)
            error_msg = f"Bocha search error: {str(e)}"
            return error_msg, {"error": str(e), "query": query}
