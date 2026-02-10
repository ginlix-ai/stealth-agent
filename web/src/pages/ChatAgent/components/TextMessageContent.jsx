import React from 'react';
import Markdown from './Markdown';

/**
 * TextMessageContent Component
 *
 * Renders text content from message_chunk events with content_type: text.
 * Supports markdown formatting including bold, italic, lists, code blocks, etc.
 *
 * @param {Object} props
 * @param {string} props.content - The text content to display (supports markdown)
 * @param {boolean} props.isStreaming - Whether the message is currently streaming
 * @param {boolean} props.hasError - Whether the message has an error
 */
function TextMessageContent({ content, isStreaming, hasError }) {
  if (!content) {
    return null;
  }

  return (
    <Markdown variant="chat" content={content || ''} className="text-base" />
  );
}

export default TextMessageContent;
