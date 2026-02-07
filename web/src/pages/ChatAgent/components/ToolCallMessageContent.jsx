import { ChevronDown, ChevronUp, Loader2, Wrench } from 'lucide-react';
import { useState } from 'react';

// File-related tool names that support opening in the file panel
const FILE_TOOLS = ['write_file', 'edit_file', 'read_file', 'save_file'];

function getFilePathFromToolCall(toolCall) {
  if (!toolCall?.args) return null;
  const args = toolCall.args;
  return args.file_path || args.path || args.filename || null;
}

/**
 * ToolCallMessageContent Component
 * 
 * Renders tool call information from tool_calls and tool_call_result events.
 * 
 * Features:
 * - Shows an icon indicating tool call status (loading when in progress, finished when complete)
 * - Displays tool name (e.g., "write_file")
 * - For file tools: clicking opens the file in the right panel via onOpenFile callback
 * - For non-file tools: clicking toggles visibility of tool call details
 * - Displays tool_calls and tool_call_result with different visual styles
 * 
 * @param {Object} props
 * @param {string} props.toolCallId - Unique identifier for this tool call
 * @param {string} props.toolName - Name of the tool (e.g., "write_file")
 * @param {Object} props.toolCall - Complete tool_calls event data
 * @param {Object} props.toolCallResult - tool_call_result event data
 * @param {boolean} props.isInProgress - Whether tool call is currently in progress
 * @param {boolean} props.isComplete - Whether tool call has completed
 * @param {boolean} props.isFailed - Whether tool call failed
 * @param {Function} props.onOpenFile - Callback to open a file in the file panel
 */
function ToolCallMessageContent({ 
  toolCallId, 
  toolName, 
  toolCall, 
  toolCallResult, 
  isInProgress, 
  isComplete,
  isFailed = false,
  onOpenFile
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Don't render if there's no tool call data
  if (!toolName && !toolCall) {
    return null;
  }

  // Determine display name and file path
  const displayName = toolName || toolCall?.name || 'Tool Call';
  const isFileTool = FILE_TOOLS.includes(displayName);
  const filePath = isFileTool ? getFilePathFromToolCall(toolCall) : null;

  const handleToggle = () => {
    // For file tools with a valid path and onOpenFile callback, open in file panel
    if (isFileTool && filePath && onOpenFile) {
      onOpenFile(filePath);
      return;
    }
    // Otherwise, toggle expand/collapse as before
    setIsExpanded(!isExpanded);
  };

  return (
    <div className="mt-2">
      {/* Tool call indicator button */}
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
          color: isFailed ? '#FF383C' : 'var(--Labels-Secondary)',
          padding: '4px 12px',
          borderRadius: '6px',
          backgroundColor: isInProgress 
            ? 'rgba(97, 85, 245, 0.15)' 
            : 'transparent',
          border: isInProgress 
            ? '1px solid rgba(255, 255, 255, 0.1)' 
            : 'none',
          width: '100%',
        }}
        title={isInProgress ? 'Tool call in progress...' : 'View tool call details'}
      >
        {/* Icon: Wrench with loading spinner when active, static wrench when complete/failed */}
        <div className="relative flex-shrink-0">
          <Wrench 
            className="h-4 w-4" 
            style={{ color: isFailed ? '#FF383C' : 'var(--Labels-Secondary)' }} 
          />
          {isInProgress && (
            <Loader2 
              className="h-3 w-3 absolute -top-0.5 -right-0.5 animate-spin" 
              style={{ color: 'var(--Labels-Secondary)' }} 
            />
          )}
        </div>
        
        {/* Tool name label */}
        <span style={{ color: 'inherit' }}>
          {displayName}
        </span>
        
        {/* Status indicator */}
        {isComplete && !isInProgress && (
          <span 
            className="text-xs" 
            style={{ 
              color: 'inherit',
              opacity: 0.8
            }}
          >
            {isFailed ? '(failed)' : '(complete)'}
          </span>
        )}
        
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

      {/* Tool call details (shown when expanded) */}
      {isExpanded && (
        <div
          className="mt-2 space-y-3"
          style={{
            backgroundColor: 'rgba(97, 85, 245, 0.1)',
            border: '1px solid rgba(97, 85, 245, 0.2)',
            borderRadius: '6px',
            padding: '12px',
          }}
        >
          {/* Tool Call (complete call data) */}
          {toolCall && (
            <div>
              <p className="text-xs  mb-2" style={{ color: '#FFFFFF', opacity: 0.8 }}>
                Tool Call:
              </p>
              <div
                className="px-3 py-2 rounded text-xs"
                style={{
                  backgroundColor: 'rgba(0, 0, 0, 0.2)',
                  color: '#FFFFFF',
                  opacity: 0.9,
                }}
              >
                <div className="mb-1">
                  <span className="">Name:</span> {toolCall.name}
                </div>
                {toolCall.args && (
                  <div className="mt-2">
                    <span className="">Arguments:</span>
                    <pre className="mt-1 font-mono text-xs whitespace-pre-wrap break-words">
                      {JSON.stringify(toolCall.args, null, 2)}
                    </pre>
                  </div>
                )}
                {toolCall.id && (
                  <div className="mt-2 text-xs" style={{ opacity: 0.7 }}>
                    <span className="">ID:</span> {toolCall.id}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tool Call Result */}
          {toolCallResult && (
            <div>
              <p className="text-xs  mb-2" style={{ color: '#FFFFFF', opacity: 0.8 }}>
                Result:
              </p>
              <div
                className="px-3 py-2 rounded text-xs whitespace-pre-wrap break-words"
                style={{
                  backgroundColor: toolCallResult.content?.includes('ERROR') 
                    ? 'rgba(255, 56, 60, 0.15)' 
                    : 'rgba(15, 237, 190, 0.15)',
                  border: `1px solid ${toolCallResult.content?.includes('ERROR') 
                    ? 'rgba(255, 56, 60, 0.3)' 
                    : 'rgba(15, 237, 190, 0.3)'}`,
                  color: '#FFFFFF',
                  opacity: 0.9,
                }}
              >
                {toolCallResult.content || 'No result content'}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ToolCallMessageContent;
