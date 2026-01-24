import React from 'react';

/**
 * TextMessageContent Component
 * 
 * Renders text content from message_chunk events with content_type: text.
 * This component is specifically designed for displaying text-based messages
 * in the chat interface.
 * 
 * @param {Object} props
 * @param {string} props.content - The text content to display
 * @param {boolean} props.isStreaming - Whether the message is currently streaming
 * @param {boolean} props.hasError - Whether the message has an error
 */
function TextMessageContent({ content, isStreaming, hasError }) {
  return (
    <p className="text-sm whitespace-pre-wrap break-words">
      {content || (isStreaming ? '...' : '')}
    </p>
  );
}

export default TextMessageContent;
