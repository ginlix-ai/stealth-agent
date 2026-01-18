"""
Message deduplication utilities for conversation API.

Handles deduplication of agent messages across conversation threads,
using both ID-based and content-based deduplication strategies.
"""

from typing import List, Dict, Any, Tuple
import logging

from src.server.utils.content_normalizer import extract_text_from_message_content

logger = logging.getLogger(__name__)

# Minimum content length for content-based deduplication
# Short messages (tool calls, etc.) are not fingerprinted
CONTENT_FINGERPRINT_MIN_LENGTH = 100

# Number of characters to use for content fingerprint
CONTENT_FINGERPRINT_LENGTH = 200


def deduplicate_agent_messages(
    message_objects: List[Any],
    message_types_to_deduplicate: List[str] = None
) -> Tuple[List[Any], int]:
    """
    Deduplicate agent messages across all query-response pairs in a conversation.

    Deduplication strategies:
    - ID-based: Skip messages with previously seen IDs
    - Content-based: For AIMessage, also skip messages with same content fingerprint
      (handles cases where same content is stored with different IDs across threads)

    Args:
        message_objects: List of ConversationMessage objects
        message_types_to_deduplicate: Message types to deduplicate
            (default: ['AIMessage', 'ToolMessage', 'HumanMessage'])

    Returns:
        Tuple of (deduplicated_message_objects, count_of_duplicates_removed)

    Example:
        >>> message_objects, removed = deduplicate_agent_messages(messages)
        >>> logger.info(f"Removed {removed} duplicate messages")
    """
    if message_types_to_deduplicate is None:
        message_types_to_deduplicate = ['AIMessage', 'ToolMessage', 'HumanMessage']

    seen_ids = set()
    seen_content_fingerprints = set()  # For content-based deduplication
    duplicates_removed = 0

    for message_pair in message_objects:
        # Skip if no response or agent_messages
        if not message_pair.response or not message_pair.response.agent_messages:
            continue

        # Iterate through each agent's messages
        for agent_name, agent_data in message_pair.response.agent_messages.items():
            if not isinstance(agent_data, dict) or 'messages' not in agent_data:
                continue

            filtered_messages = []

            for msg in agent_data['messages']:
                msg_id = msg.get('id')
                msg_type = msg.get('type')

                # Only deduplicate specified message types
                if msg_type in message_types_to_deduplicate:
                    # Check for ID-based duplicate
                    is_id_duplicate = msg_id and msg_id in seen_ids

                    # Check for content-based duplicate (for AIMessage/HumanMessage with text)
                    content_fingerprint = None
                    is_content_duplicate = False

                    if msg_type in ('AIMessage', 'HumanMessage'):
                        # Extract text from content (handles both string and list formats)
                        content = extract_text_from_message_content(msg.get('content', ''))

                        if content and len(content) >= CONTENT_FINGERPRINT_MIN_LENGTH:
                            # Use first N chars as fingerprint
                            content_fingerprint = hash(content[:CONTENT_FINGERPRINT_LENGTH])
                            is_content_duplicate = content_fingerprint in seen_content_fingerprints

                    # Skip if either ID or content is duplicate
                    if is_id_duplicate or is_content_duplicate:
                        duplicates_removed += 1
                        reason = "id" if is_id_duplicate else "content"
                        logger.debug(
                            f"Skipped duplicate {msg_type} ({reason}-based) "
                            f"id={msg_id} from agent={agent_name}"
                        )
                    else:
                        # First occurrence - keep it and track
                        if msg_id:
                            seen_ids.add(msg_id)
                        if content_fingerprint:
                            seen_content_fingerprints.add(content_fingerprint)
                        filtered_messages.append(msg)
                else:
                    # Other message types - keep all occurrences
                    filtered_messages.append(msg)

            # Update agent's messages with filtered list
            agent_data['messages'] = filtered_messages

    return message_objects, duplicates_removed
