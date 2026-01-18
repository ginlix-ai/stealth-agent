"""
Per-call token usage tracker for accurate tiered pricing.

This module provides a custom callback handler that tracks token usage with per-call
granularity, enabling accurate cost calculation for models with tiered pricing,
2D matrix pricing, or input-dependent pricing.

Unlike LangChain's default UsageMetadataCallbackHandler which aggregates tokens
immediately, this tracker preserves per-call records before aggregation, allowing
accurate pricing where rates vary based on token counts.
"""

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.messages.ai import UsageMetadata, add_usage
from langchain_core.outputs import ChatGeneration, LLMResult

from src.llms.token_counter import extract_token_usage

logger = logging.getLogger(__name__)


class PerCallTokenTracker(BaseCallbackHandler):
    """
    Tracks LLM token usage with per-call granularity for accurate tiered pricing.

    This callback handler captures token usage from each individual LLM call before
    aggregation, enabling accurate cost calculation for models with:
    - Tiered pricing (different rates based on token count thresholds)
    - 2D matrix pricing (rates vary by both input and output token counts)
    - Input-dependent output pricing (output rate based on input tier)

    The tracker maintains both:
    1. per_call_records: List of individual call records for accurate pricing
    2. usage_metadata: Aggregated usage by model for backward compatibility

    Example:
        >>> tracker = PerCallTokenTracker()
        >>> # Use in LangGraph workflow
        >>> result = workflow.invoke(input, config={"callbacks": [tracker]})
        >>> # Calculate accurate costs from per-call records
        >>> costs = calculate_cost_from_per_call_records(tracker.per_call_records)
    """

    def __init__(self) -> None:
        """Initialize the tracker with empty per-call records and aggregated metadata."""
        super().__init__()
        self._lock = threading.Lock()
        self.per_call_records: List[Dict[str, Any]] = []
        self.usage_metadata: Dict[str, UsageMetadata] = {}

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """
        Callback invoked after an LLM completes.

        Captures token usage metadata from the response and stores both:
        1. Per-call record with full metadata
        2. Aggregated usage by model (for compatibility)

        Args:
            response: The LLM response containing usage metadata
            run_id: Unique identifier for this LLM run
            parent_run_id: Identifier of the parent run (if nested)
            **kwargs: Additional callback arguments
        """
        if not response.generations or not response.generations[0]:
            return

        generation = response.generations[0][0]
        if not isinstance(generation, ChatGeneration):
            return

        message = generation.message
        if not isinstance(message, AIMessage):
            return

        # Use extract_token_usage() for robust token extraction across providers
        # Handles Anthropic, OpenAI, Gemini formats with proper field normalization
        usage_metadata = extract_token_usage(message)
        if not usage_metadata:
            return

        # Extract model name from response metadata
        model_name = message.response_metadata.get("model_name")
        if not model_name:
            # Fallback to model_name in response.llm_output if available
            if response.llm_output:
                model_name = response.llm_output.get("model_name")

        if not model_name:
            logger.warning(
                f"No model_name found in response metadata for run {run_id}, "
                "skipping token tracking"
            )
            return

        with self._lock:
            # Store per-call record
            self.per_call_records.append({
                "model_name": model_name,
                "usage": usage_metadata,
                "timestamp": datetime.now().isoformat(),
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
            })

            # Also maintain aggregated usage for backward compatibility
            if model_name not in self.usage_metadata:
                self.usage_metadata[model_name] = usage_metadata
            else:
                self.usage_metadata[model_name] = add_usage(
                    self.usage_metadata[model_name], usage_metadata
                )

    def get_aggregated_usage(self) -> Dict[str, UsageMetadata]:
        """
        Get aggregated token usage by model.

        This method provides backward compatibility with code expecting
        aggregated usage data.

        Returns:
            Dictionary mapping model names to aggregated UsageMetadata
        """
        with self._lock:
            return self.usage_metadata.copy()

    def get_per_call_records(self) -> List[Dict[str, Any]]:
        """
        Get list of per-call token usage records.

        Returns:
            List of dictionaries containing:
            - model_name: str
            - usage: UsageMetadata
            - timestamp: str (ISO format)
            - run_id: str
            - parent_run_id: Optional[str]
        """
        with self._lock:
            return self.per_call_records.copy()

    def reset(self) -> None:
        """
        Reset all tracked data.

        Clears both per-call records and aggregated usage metadata.
        Useful for reusing the same tracker across multiple workflow runs.
        """
        with self._lock:
            self.per_call_records.clear()
            self.usage_metadata.clear()

    def __repr__(self) -> str:
        """String representation showing number of calls and models tracked."""
        with self._lock:
            num_calls = len(self.per_call_records)
            num_models = len(self.usage_metadata)
        return f"PerCallTokenTracker(calls={num_calls}, models={num_models})"
