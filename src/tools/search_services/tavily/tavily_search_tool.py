import logging
import json
from typing import Dict, List, Optional, Tuple, Union, Literal

from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re

from src.tools.search_services.tavily.tavily_search_api_wrapper import (
    EnhancedTavilySearchAPIWrapper, )

logger = logging.getLogger(__name__)


class TavilySearchInput(BaseModel):
    """Input schema for Tavily search tool with time filtering."""

    query: str = Field(
        description="Search query to look up"
    )

    time_range: Optional[Literal["day", "week", "month", "year", "d", "w", "m", "y"]] = Field(
        default=None,
        description=(
            "Time range filter for search results. Options: "
            "'day'/'d' (last 24 hours), 'week'/'w' (last 7 days), "
            "'month'/'m' (last 30 days), 'year'/'y' (last 365 days). "
            "Note: If start_date or end_date is provided, time_range will be ignored."
        )
    )

    start_date: Optional[str] = Field(
        default=None,
        description=(
            "Start date for search results in YYYY-MM-DD format (e.g., '2025-01-15'). "
            "When provided with end_date, filters results to this date range. "
            "Takes priority over time_range parameter."
        )
    )

    end_date: Optional[str] = Field(
        default=None,
        description=(
            "End date for search results in YYYY-MM-DD format (e.g., '2025-01-31'). "
            "When provided with start_date, filters results to this date range. "
            "Takes priority over time_range parameter."
        )
    )

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate date format is YYYY-MM-DD."""
        if v is None:
            return v

        # Check format with regex
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', v):
            raise ValueError(
                f"Date must be in YYYY-MM-DD format, got: {v}"
            )

        # Validate it's a valid date
        try:
            from datetime import datetime
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError as e:
            raise ValueError(f"Invalid date: {v}. {str(e)}")

        return v


class TavilySearchTool(EnhancedTavilySearchAPIWrapper
                       ):  # type: ignore[override, override]
    """Tool that queries the Tavily Search API and gets back json.

    Returns a tuple of (cleaned_results, filtered_artifact):
    - cleaned_results: Formatted for LLM consumption (includes URLs, content, but excludes favicon)
    - filtered_artifact: Metadata for frontend (includes favicon, excludes content/raw_content to avoid duplication)
    """

    # Enable artifact pattern to provide raw_results with favicon to frontend
    response_format: str = "content_and_artifact"

    # Set custom args schema for LLM-callable parameters
    args_schema: type[BaseModel] = TavilySearchInput

    include_image_descriptions: bool = False
    """Include a image descriptions in the response.

    Default is False.
    """

    include_favicon: bool = True
    """Include favicon URLs in raw_results artifact.

    Default is True. When enabled, raw_results will include favicon URLs
    for each search result. Favicon URLs are NOT included in cleaned_results
    (LLM-visible content), only in the artifact for frontend use.
    """

    verbose: bool = True
    """Control verbosity of search results at initialization time.

    - True (default): Include images, raw_content, image descriptions (comprehensive results)
    - False: Text-only results without images or raw_content (lightweight for planning)

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

    api_wrapper: EnhancedTavilySearchAPIWrapper = Field(
        default_factory=EnhancedTavilySearchAPIWrapper
    )  # type: ignore[arg-type]

    def _filter_artifact_for_frontend(self, raw_results: Dict) -> Dict:
        """Remove duplicated content fields from artifact.

        The artifact is sent to frontend alongside cleaned_results.
        Since cleaned_results already contains content/raw_content/score,
        we remove these fields from the artifact to avoid duplication.

        Keeps: query, answer, images, response_time, follow_up_questions,
               results[].title, results[].url, results[].favicon
        Removes: results[].content, results[].raw_content, results[].score

        Args:
            raw_results: Complete API response from Tavily

        Returns:
            Filtered artifact with content fields removed from results array
        """
        filtered = raw_results.copy()

        if "results" in filtered:
            filtered["results"] = [
                {
                    k: v
                    for k, v in result.items()
                    if k not in ("content", "raw_content", "score")
                }
                for result in filtered["results"]
            ]

        return filtered

    async def _arun(
        self,
        query: str,
        time_range: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        topic: Optional[str] = "general",
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> Tuple[Union[List[Dict[str, str]], str], Dict]:
        """Use the tool asynchronously with time and topic filtering.

        Args:
            query: Search query string
            time_range: Time range filter (d/w/m/y). Ignored if start_date or end_date provided.
            start_date: Start date in YYYY-MM-DD format. Takes priority over time_range.
            end_date: End date in YYYY-MM-DD format. Takes priority over time_range.
            topic: Search topic (general/news/finance)
            run_manager: Optional callback manager

        Returns:
            Tuple of (cleaned_results, filtered_artifact):
            - cleaned_results: List of result dicts for LLM (includes URLs and content, excludes favicon)
            - filtered_artifact: Metadata dict for frontend (includes favicon, excludes content/raw_content)
        """
        # Prioritization logic: dates > LLM time_range > default_time_range
        effective_time_range = None
        effective_start_date = None
        effective_end_date = None

        if start_date or end_date:
            # Use dates if provided (highest priority)
            effective_start_date = start_date
            effective_end_date = end_date
            logger.debug(
                f"Using date range: start_date={start_date}, end_date={end_date} "
                f"(ignoring time_range={time_range}, default={self.default_time_range})"
            )
        else:
            # Use LLM-provided time_range, or fall back to default
            effective_time_range = time_range or self.default_time_range
            logger.debug(
                f"Using time_range: {effective_time_range} "
                f"(LLM: {time_range}, default: {self.default_time_range})"
            )

        # Verbosity control: determine what to include based on self.verbose (set at init)
        # Always disable raw_content to reduce response size
        include_raw_content = False
        if self.verbose:
            include_images = True
            include_image_descriptions = True
            logger.debug("Verbose mode: including images (raw_content disabled)")
        else:
            include_images = False
            include_image_descriptions = False
            logger.debug("Lightweight mode: text-only results")

        try:
            raw_results = await self.api_wrapper.raw_results(
                query,
                self.max_results,
                self.search_depth,
                self.include_domains,
                self.exclude_domains,
                self.include_answer,
                include_raw_content,
                include_images,
                include_image_descriptions,
                include_favicon=self.include_favicon,
                time_range=effective_time_range,
                start_date=effective_start_date,
                end_date=effective_end_date,
                topic=topic,
            )
        except Exception as e:
            return repr(e), {}

        cleaned_results = await self.api_wrapper.clean_results_with_images(
            raw_results)
        logger.debug("search results: %s",
                     json.dumps(cleaned_results, indent=2, ensure_ascii=False))

        # Record images with descriptions for the current query context
        try:
            from src.subgraphs.iterative_research.image_store import record_image
            if isinstance(cleaned_results, list):
                for item in cleaned_results:
                    if isinstance(item, dict) and item.get("type") == "image":
                        url = item.get("image_url") or ""
                        desc = item.get("image_description") or ""
                        if url and desc:
                            record_image(url, desc)
        except Exception:
            pass

        # Filter artifact to remove duplicated content fields
        filtered_artifact = self._filter_artifact_for_frontend(raw_results)

        return cleaned_results, filtered_artifact
