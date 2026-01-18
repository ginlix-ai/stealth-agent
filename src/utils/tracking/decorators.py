"""
Tracking decorators for execution monitoring.

Provides decorators for automatic tracking of:
- Messages from function results
- Tool calls from agent executions
- Complete execution metrics and status
- LangGraph node execution tracking
"""

import asyncio
import functools
import logging
from typing import Any, Callable, Optional, TypeVar

from .core import ExecutionTracker, ToolCallProcessor, ExecutionAnalyzer

logger = logging.getLogger(__name__)

# Type variables for decorators
F = TypeVar('F', bound=Callable[..., Any])


# ============================================================================
# Tracking Decorators
# ============================================================================

def track_messages(
    message_key: str = "messages",
    start_tracking: bool = True
) -> Callable[[F], F]:
    """
    Decorator to extract and track messages from function result.

    Args:
        message_key: Key to extract messages from result dict
        start_tracking: Whether to start a new tracking context

    Usage:
        @track_messages(message_key='messages')
        async def my_function(state):
            ...
            return {'messages': [...]}
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if start_tracking:
                ExecutionTracker.start_tracking()

            result = await func(*args, **kwargs)

            # Extract messages from result
            if isinstance(result, dict) and message_key in result:
                messages = result[message_key]
                ExecutionTracker.update_context(messages=messages)

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if start_tracking:
                ExecutionTracker.start_tracking()

            result = func(*args, **kwargs)

            # Extract messages from result
            if isinstance(result, dict) and message_key in result:
                messages = result[message_key]
                ExecutionTracker.update_context(messages=messages)

            return result

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


def track_tool_calls(
    auto_extract: bool = True,
    processor: Optional[ToolCallProcessor] = None
) -> Callable[[F], F]:
    """
    Decorator to extract and track tool calls from messages.

    Args:
        auto_extract: Whether to automatically extract tool calls from tracked messages
        processor: Custom ToolCallProcessor instance (uses default if None)

    Usage:
        @track_tool_calls()
        async def researcher_node(state):
            ...
            return result
    """
    if processor is None:
        processor = ToolCallProcessor()

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            # Extract tool calls if auto_extract is enabled
            if auto_extract:
                messages = ExecutionTracker.get_messages()
                if messages:
                    tool_calls = processor.extract_tool_calls(messages)
                    ExecutionTracker.update_context(tool_calls=tool_calls)

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Extract tool calls if auto_extract is enabled
            if auto_extract:
                messages = ExecutionTracker.get_messages()
                if messages:
                    tool_calls = processor.extract_tool_calls(messages)
                    ExecutionTracker.update_context(tool_calls=tool_calls)

            return result

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


def track_execution(
    extract_messages: bool = True,
    extract_tool_calls: bool = True,
    calculate_metrics: bool = True,
    message_key: str = "messages",
    task_type: Optional[str] = None,
    attach_to_result: bool = False,
    result_key: str = "_tracking"
) -> Callable[[F], F]:
    """
    Complete execution tracking decorator.

    Tracks messages, tool calls, metrics, execution time, and status.

    Args:
        extract_messages: Whether to extract messages from result
        extract_tool_calls: Whether to extract tool calls
        calculate_metrics: Whether to calculate execution metrics
        message_key: Key to extract messages from result dict
        task_type: Task type for status determination (e.g., "researcher", "coder")
        attach_to_result: Whether to attach tracking data to result
        result_key: Key to use when attaching tracking data

    Usage:
        @track_execution(task_type="researcher")
        async def execute_research_task(task):
            ...
            return {'messages': [...], 'output': '...'}

        # Later access via:
        tracker = get_tracker()
        metrics = tracker.get_metrics()
    """
    processor = ToolCallProcessor()
    analyzer = ExecutionAnalyzer()

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Start tracking
            ExecutionTracker.start_tracking()

            try:
                result = await func(*args, **kwargs)

                # Extract messages if enabled
                messages = []
                if extract_messages and isinstance(result, dict) and message_key in result:
                    messages = result[message_key]
                    ExecutionTracker.update_context(messages=messages)

                # Extract tool calls if enabled
                tool_calls = []
                if extract_tool_calls and messages:
                    tool_calls = processor.extract_tool_calls(messages)
                    ExecutionTracker.update_context(tool_calls=tool_calls)

                # Calculate metrics if enabled
                if calculate_metrics:
                    final_output = result.get('final_output', '') if isinstance(result, dict) else ''
                    analysis = analyzer.analyze(
                        messages=messages,
                        final_output=final_output,
                        tool_calls=tool_calls,
                        task_type=task_type
                    )

                    ExecutionTracker.update_context(
                        metrics=analysis['metrics'],
                        status=analysis['status'],
                        errors=analysis['errors'],
                        warnings=analysis['warnings']
                    )

                # Attach tracking data to result if requested
                if attach_to_result and isinstance(result, dict):
                    context = ExecutionTracker.get_context()
                    if context:
                        result[result_key] = {
                            'messages': context.messages,
                            'tool_calls': context.tool_calls,
                            'metrics': context.metrics,
                            'status': context.status,
                            'execution_time': context.execution_time,
                            'errors': context.errors,
                            'warnings': context.warnings
                        }

                return result

            except Exception as e:
                # Track the error
                ExecutionTracker.update_context(
                    status="error",
                    errors=[str(e)]
                )
                raise

            finally:
                # Stop tracking
                ExecutionTracker.stop_tracking()

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Start tracking
            ExecutionTracker.start_tracking()

            try:
                result = func(*args, **kwargs)

                # Extract messages if enabled
                messages = []
                if extract_messages and isinstance(result, dict) and message_key in result:
                    messages = result[message_key]
                    ExecutionTracker.update_context(messages=messages)

                # Extract tool calls if enabled
                tool_calls = []
                if extract_tool_calls and messages:
                    tool_calls = processor.extract_tool_calls(messages)
                    ExecutionTracker.update_context(tool_calls=tool_calls)

                # Calculate metrics if enabled
                if calculate_metrics:
                    final_output = result.get('final_output', '') if isinstance(result, dict) else ''
                    analysis = analyzer.analyze(
                        messages=messages,
                        final_output=final_output,
                        tool_calls=tool_calls,
                        task_type=task_type
                    )

                    ExecutionTracker.update_context(
                        metrics=analysis['metrics'],
                        status=analysis['status'],
                        errors=analysis['errors'],
                        warnings=analysis['warnings']
                    )

                # Attach tracking data to result if requested
                if attach_to_result and isinstance(result, dict):
                    context = ExecutionTracker.get_context()
                    if context:
                        result[result_key] = {
                            'messages': context.messages,
                            'tool_calls': context.tool_calls,
                            'metrics': context.metrics,
                            'status': context.status,
                            'execution_time': context.execution_time,
                            'errors': context.errors,
                            'warnings': context.warnings
                        }

                return result

            except Exception as e:
                # Track the error
                ExecutionTracker.update_context(
                    status="error",
                    errors=[str(e)]
                )
                raise

            finally:
                # Stop tracking
                ExecutionTracker.stop_tracking()

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


def track_node(
    extract_tool_calls: bool = True,
    task_type: Optional[str] = None,
    agent_name: Optional[str] = None
) -> Callable[[F], F]:
    """
    Specialized decorator for LangGraph node functions.

    Tracks tool calls and execution from node state updates.

    Args:
        extract_tool_calls: Whether to extract tool calls from node messages
        task_type: Task type for metrics (e.g., "researcher", "coder")
        agent_name: Agent name for organizing messages (e.g., "planner", "reporter")

    Usage:
        @track_node(agent_name="planner")
        async def planner_node(state: State):
            ...
            return {'messages': [...]}
    """
    processor = ToolCallProcessor()

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get existing messages from state if available
            state = args[0] if args else kwargs.get('state', {})
            existing_messages = state.get('messages', []) if isinstance(state, dict) else []

            result = await func(*args, **kwargs)

            # Extract update dict from result (handle both dict and Command objects)
            update_dict = None
            if isinstance(result, dict):
                update_dict = result
            elif hasattr(result, 'update'):  # Command object
                update_dict = result.update

            # Extract new messages from update dict
            if update_dict and 'messages' in update_dict:
                new_messages = update_dict['messages']
                all_messages = existing_messages + new_messages

                # Track messages with agent name if provided
                if agent_name:
                    ExecutionTracker.update_context(
                        agent_name=agent_name,
                        messages=new_messages  # Track only new messages from this node
                    )
                else:
                    ExecutionTracker.update_context(messages=all_messages)

                # Extract tool calls if enabled
                if extract_tool_calls:
                    tool_calls = processor.extract_tool_calls(all_messages)
                    ExecutionTracker.update_context(tool_calls=tool_calls)

                # Store task type in metadata
                if task_type:
                    ExecutionTracker.update_context(metadata={'task_type': task_type})

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Get existing messages from state if available
            state = args[0] if args else kwargs.get('state', {})
            existing_messages = state.get('messages', []) if isinstance(state, dict) else []

            result = func(*args, **kwargs)

            # Extract update dict from result (handle both dict and Command objects)
            update_dict = None
            if isinstance(result, dict):
                update_dict = result
            elif hasattr(result, 'update'):  # Command object
                update_dict = result.update

            # Extract new messages from update dict
            if update_dict and 'messages' in update_dict:
                new_messages = update_dict['messages']
                all_messages = existing_messages + new_messages

                # Track messages with agent name if provided
                if agent_name:
                    ExecutionTracker.update_context(
                        agent_name=agent_name,
                        messages=new_messages  # Track only new messages from this node
                    )
                else:
                    ExecutionTracker.update_context(messages=all_messages)

                # Extract tool calls if enabled
                if extract_tool_calls:
                    tool_calls = processor.extract_tool_calls(all_messages)
                    ExecutionTracker.update_context(tool_calls=tool_calls)

                # Store task type in metadata
                if task_type:
                    ExecutionTracker.update_context(metadata={'task_type': task_type})

            return result

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


# Public API
__all__ = [
    'track_messages',
    'track_tool_calls',
    'track_execution',
    'track_node',
]
