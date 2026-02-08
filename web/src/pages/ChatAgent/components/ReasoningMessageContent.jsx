import React, { useState } from 'react';
import { Brain, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * ReasoningMessageContent Component
 * 
 * Renders reasoning content from message_chunk events with content_type: reasoning.
 * 
 * Features:
 * - Shows an icon indicating reasoning status (loading when active, finished when complete)
 * - Clickable icon to toggle visibility of reasoning content
 * - Reasoning content is folded by default, can be expanded on click
 * 
 * @param {Object} props
 * @param {string} props.reasoningContent - The accumulated reasoning content
 * @param {boolean} props.isReasoning - Whether reasoning is currently in progress
 * @param {boolean} props.reasoningComplete - Whether reasoning process has completed
 * @param {string|null} [props.reasoningTitle] - Optional title extracted from **...** in content (live streaming only; history does not pass this)
 */
function ReasoningMessageContent({ reasoningContent, isReasoning, reasoningComplete, reasoningTitle }) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Don't render if there's no reasoning content, reasoning hasn't started, and reasoning isn't complete
  if (!reasoningContent && !isReasoning && !reasoningComplete) {
    return null;
  }

  const handleToggle = () => {
    setIsExpanded(!isExpanded);
  };

  return (
    <div className="mt-2">
      {/* Reasoning indicator button */}
      <button
        onClick={handleToggle}
        className="transition-colors hover:bg-white/10"
        style={{
          boxSizing: 'border-box',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '14px',
          lineHeight: '20px',
          color: 'var(--Labels-Secondary)',
          padding: '4px 12px',
          borderRadius: '6px',
          backgroundColor: isReasoning 
            ? 'rgba(97, 85, 245, 0.15)' 
            : 'transparent',
          border: isReasoning 
            ? '1px solid rgba(255, 255, 255, 0.1)' 
            : 'none',
          width: '100%',
        }}
        title={isReasoning ? 'Reasoning in progress...' : 'View reasoning process'}
      >
        {/* Icon: Brain with loading spinner when active, static brain when complete */}
        <div className="relative flex-shrink-0">
          <Brain className="h-4 w-4" style={{ color: 'var(--Labels-Secondary)' }} />
          {isReasoning && (
            <Loader2 
              className="h-3 w-3 absolute -top-0.5 -right-0.5 animate-spin" 
              style={{ color: 'var(--Labels-Secondary)' }} 
            />
          )}
        </div>
        
        {/* Label: when complete show "Reasoning"; when streaming and title present show "Reasoning: Title"; else "Reasoning..." or "Reasoning" */}
        <span style={{ color: 'inherit' }} className="truncate min-w-0">
          {reasoningComplete
            ? 'Reasoning'
            : reasoningTitle
              ? `Reasoning: ${reasoningTitle}`
              : isReasoning
                ? 'Reasoning...'
                : 'Reasoning'}
        </span>
        
        {/* Expand/collapse icon */}
        <div
          style={{
            flexShrink: 0,
            color: 'var(--Labels-Quaternary)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          {isExpanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </div>
      </button>

      {/* Reasoning content (shown when expanded) - vertical line on left, no box */}
      {isExpanded && reasoningContent && (
        <div
          className="mt-2 pl-3 pr-0 py-1 text-xs reasoning-markdown"
          style={{
            borderLeft: '3px solid rgba(97, 85, 245, 0.5)',
            color: '#FFFFFF',
            opacity: 0.9,
          }}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ node, ...props }) => (
                <p className="my-[1px] py-[3px] whitespace-pre-wrap break-words first:mt-0 last:mb-0" style={{ color: '#FFFFFF' }} {...props} />
              ),
              strong: ({ node, ...props }) => (
                <strong className="font-[600]" style={{ color: '#FFFFFF' }} {...props} />
              ),
              em: ({ node, ...props }) => (
                <em className="italic" style={{ color: '#FFFFFF' }} {...props} />
              ),
              code: ({ node, className, children, ...props }) => {
                const isBlock = /language-/.test(className || '');
                if (!isBlock) {
                  return (
                    <code className="font-mono" style={{ color: '#abb2bf', fontSize: 'inherit' }} {...props}>
                      {children}
                    </code>
                  );
                }
                return (
                  <code className="font-mono" style={{ color: '#abb2bf', fontSize: 'inherit' }} {...props}>
                    {children}
                  </code>
                );
              },
              pre: ({ node, ...props }) => (
                <pre className="rounded overflow-x-auto my-1 py-1 px-2" style={{ backgroundColor: 'rgba(0,0,0,0.2)', margin: 0 }} {...props} />
              ),
              ul: ({ node, ...props }) => <ul className="list-disc ml-4 my-1" style={{ color: '#FFFFFF' }} {...props} />,
              ol: ({ node, ...props }) => <ol className="list-decimal ml-4 my-1" style={{ color: '#FFFFFF' }} {...props} />,
              li: ({ node, ...props }) => <li className="break-words" style={{ color: '#FFFFFF' }} {...props} />,
            }}
          >
            {reasoningContent}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}

export default ReasoningMessageContent;
