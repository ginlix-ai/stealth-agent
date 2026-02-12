import React from 'react';
import { AlertTriangle } from 'lucide-react';
import Markdown from './Markdown';
import { useAnimatedText } from '@/components/ui/animated-text';
import { parseErrorMessage } from '../utils/parseErrorMessage';

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
  const displayText = useAnimatedText(content || '', { enabled: isStreaming });

  if (!content) {
    return null;
  }

  if (hasError) {
    const parsed = parseErrorMessage(content);
    return <ErrorDisplay parsed={parsed} />;
  }

  return (
    <Markdown variant="chat" content={displayText} className="text-base" />
  );
}

/**
 * ErrorDisplay Component
 *
 * Renders a parsed error message in a clean, structured format.
 */
function ErrorDisplay({ parsed }) {
  return (
    <div
      className="flex gap-3 px-4 py-3 rounded-lg text-sm"
      style={{
        backgroundColor: 'rgba(220, 38, 38, 0.08)',
        border: '1px solid rgba(220, 38, 38, 0.2)',
      }}
    >
      <AlertTriangle
        className="h-5 w-5 flex-shrink-0 mt-0.5"
        style={{ color: 'rgba(255, 120, 120, 0.9)' }}
      />
      <div className="min-w-0 space-y-1">
        <div className="font-medium" style={{ color: 'rgba(255, 180, 180, 0.95)' }}>
          {parsed.title}
        </div>
        {parsed.detail && (
          <div style={{ color: 'rgba(255, 255, 255, 0.6)' }}>
            {parsed.detail}
          </div>
        )}
        {parsed.model && (
          <div
            className="inline-block px-2 py-0.5 rounded text-xs mt-1"
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.06)',
              color: 'rgba(255, 255, 255, 0.45)',
            }}
          >
            {parsed.model}
            {parsed.statusCode ? ` · ${parsed.statusCode}` : ''}
          </div>
        )}
      </div>
    </div>
  );
}

export default TextMessageContent;
export { parseErrorMessage, ErrorDisplay };
