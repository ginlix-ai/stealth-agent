import { ChevronDown, ChevronUp, FileText } from 'lucide-react';
import { TextShimmer } from '@/components/ui/text-shimmer';
import { useState } from 'react';
import { getDisplayName, getToolIcon, getInProgressText, stripLineNumbers, parseTruncatedResult } from './toolDisplayConfig';
import Markdown from './Markdown';

/**
 * File-related tool names that support opening in the file panel.
 * Backend uses PascalCase (LangChain SDK convention). Include both for backward compatibility
 * with older history that may have snake_case tool names.
 */
const FILE_TOOLS = ['Write', 'Edit', 'Read', 'Save', 'write_file', 'edit_file', 'read_file', 'save_file'];

/**
 * Inline tools — results are shown as a one-line summary directly in the row.
 * No expand/collapse, no chevron.
 */
const INLINE_TOOLS = new Set(['Glob', 'Grep', 'Write', 'Read', 'Edit', 'ExecuteCode']);

/**
 * Extracts a short inline summary from a tool result for inline display.
 * Returns null if no summary can be extracted (falls back to normal rendering).
 */
function getInlineSummary(toolName, resultContent, toolCall) {
  if (!resultContent) return null;
  const content = typeof resultContent === 'string' ? resultContent : String(resultContent);

  switch (toolName) {
    case 'Glob': {
      return content.split('\n')[0];
    }
    case 'Grep': {
      return content.split('\n')[0];
    }
    case 'Write': {
      return content.split('\n')[0];
    }
    case 'Read': {
      const fp = toolCall?.args?.file_path || toolCall?.args?.filePath || '';
      const name = fp.split('/').pop() || 'file';
      const lineCount = content.split('\n').length;
      return `${name} (${lineCount} lines)`;
    }
    case 'Edit': {
      return content.split('\n')[0];
    }
    case 'ExecuteCode': {
      const firstLine = content.split('\n')[0];
      if (firstLine.startsWith('SUCCESS')) {
        const secondLine = content.split('\n')[1];
        return secondLine ? `SUCCESS: ${secondLine}` : 'SUCCESS';
      }
      if (firstLine.startsWith('ERROR')) {
        const secondLine = content.split('\n')[1];
        return secondLine ? `ERROR: ${secondLine}` : 'ERROR';
      }
      return firstLine;
    }
    default:
      return null;
  }
}

/**
 * Returns a short summary for expandable (non-inline) tools when complete.
 */
function getExpandableSummary(toolName, displayProcess) {
  if (!displayProcess.isComplete || displayProcess.isFailed) return null;

  if (toolName === 'WebFetch') {
    try {
      const url = displayProcess.toolCall?.args?.url;
      const domain = url ? new URL(url).hostname : null;
      return domain ? `fetched ${domain}` : null;
    } catch {
      return null;
    }
  }

  if (toolName === 'WebSearch') {
    const query = displayProcess.toolCall?.args?.query || displayProcess.toolCallResult?.artifact?.query || '';
    const queryLabel = query ? ` for '${query}'` : '';
    const content = displayProcess.toolCallResult?.content;
    if (content) {
      try {
        const results = JSON.parse(typeof content === 'string' ? content : String(content));
        if (Array.isArray(results)) {
          return `${results.length} result(s)${queryLabel}`;
        }
      } catch {
        // Not JSON
      }
    }
    return query ? `results${queryLabel}` : null;
  }

  return null;
}

/**
 * Formats raw tool result content into readable markdown for the expanded view.
 */
function formatExpandedContent(toolName, proc) {
  if (toolName !== 'WebSearch') return null;

  const raw = proc.toolCallResult?.content;
  if (!raw) return null;

  let results;
  try {
    results = JSON.parse(typeof raw === 'string' ? raw : String(raw));
    if (!Array.isArray(results)) return null;
  } catch {
    return null;
  }

  const artifact = proc.toolCallResult?.artifact;
  const richResults = artifact?.results;

  const lines = [];

  if (artifact?.answer_box) {
    const ab = artifact.answer_box;
    if (ab.answer || ab.snippet) {
      lines.push(`> ${ab.answer || ab.snippet}`);
      lines.push('');
    }
  }
  if (artifact?.knowledge_graph?.description) {
    lines.push(`> ${artifact.knowledge_graph.description}`);
    lines.push('');
  }

  results.forEach((item, i) => {
    const title = item.title || 'Untitled';
    const url = item.url || '';
    const snippet = (richResults && richResults[i]?.snippet) || item.content || '';
    const date = item.date || '';

    lines.push(`**${i + 1}. [${title}](${url})**`);
    if (snippet) lines.push(snippet);
    if (date) lines.push(`*${date}*`);
    lines.push('');
  });

  return lines.join('\n').trim() || null;
}

function getFilePathFromToolCall(toolCall) {
  if (!toolCall?.args) return null;
  const args = toolCall.args;
  return args.file_path || args.filePath || args.path || args.filename || null;
}

/**
 * ToolCallMessageContent Component
 *
 * Renders tool call information. Used in the agent panel (non-textOnly mode).
 * In the main chat textOnly mode, tool calls are rendered via ActivityAccordion/LiveActivity instead.
 *
 * @param {Object} props
 * @param {string} props.toolCallId - Unique identifier for this tool call
 * @param {string} props.toolName - Name of the tool
 * @param {Object} props.toolCall - Complete tool_calls event data
 * @param {Object} props.toolCallResult - tool_call_result event data
 * @param {boolean} props.isInProgress - Whether tool call is currently in progress
 * @param {boolean} props.isComplete - Whether tool call has completed
 * @param {boolean} props.isFailed - Whether tool call failed
 * @param {Function} props.onOpenFile - Callback to open a file in the file panel
 * @param {Array} [props.mergedProcesses] - When set, expanded view shows all tool calls + results in order
 */
function ToolCallMessageContent({
  toolCallId,
  toolName,
  toolCall,
  toolCallResult,
  isInProgress,
  isComplete,
  isFailed = false,
  onOpenFile,
  onDetailClick,
  mergedProcesses
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Resolve display data: single from props or last of merged
  const processes = mergedProcesses && mergedProcesses.length > 0
    ? mergedProcesses
    : [{ toolName, toolCall, toolCallResult, isInProgress, isComplete, isFailed }];
  const displayProcess = processes[processes.length - 1];
  const rawToolName = displayProcess.toolName || displayProcess.toolCall?.name || 'Tool Call';
  const displayName = getDisplayName(rawToolName);
  const isFileTool = FILE_TOOLS.includes(rawToolName);
  const filePath = isFileTool ? getFilePathFromToolCall(displayProcess.toolCall) : null;

  // Don't render if there's no tool call data
  if (!rawToolName && !displayProcess.toolCall) {
    return null;
  }

  // Check if this is an inline tool (result shown as summary, no expand/collapse)
  const isInlineTool = INLINE_TOOLS.has(rawToolName);
  const inlineSummaries = isInlineTool
    ? processes
        .map((proc) => {
          const content = proc.toolCallResult?.content;
          return content ? getInlineSummary(proc.toolName || rawToolName, content, proc.toolCall) : null;
        })
        .filter(Boolean)
    : [];
  const hasInlineResult = inlineSummaries.length > 0;

  const IconComponent = getToolIcon(rawToolName);

  // Inline tool rendering — compact row with summary
  if (isInlineTool) {
    const isClickable = isFileTool && filePath && onOpenFile;
    const Tag = isClickable ? 'button' : 'div';

    return (
      <div className="mt-2">
        <Tag
          {...(isClickable ? { onClick: () => onOpenFile(filePath) } : {})}
          className={isClickable ? 'transition-colors hover:bg-foreground/10' : ''}
          style={{
            boxSizing: 'border-box',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '8px',
            fontSize: '14px',
            lineHeight: '20px',
            color: displayProcess.isFailed ? 'var(--color-loss)' : 'var(--Labels-Secondary)',
            padding: '4px 12px',
            borderRadius: '6px',
            backgroundColor: displayProcess.isInProgress
              ? 'var(--color-accent-soft)'
              : 'transparent',
            border: displayProcess.isInProgress
              ? '1px solid var(--color-border-muted)'
              : 'none',
            ...(isClickable ? { cursor: 'pointer', width: '100%', textAlign: 'left' } : {}),
          }}
        >
          {/* Icon */}
          <div className="flex-shrink-0" style={{ marginTop: '2px' }}>
            <IconComponent
              className="h-4 w-4"
              style={{ color: displayProcess.isFailed ? 'var(--color-loss)' : 'var(--Labels-Secondary)' }}
            />
          </div>

          {/* Tool name + inline summary */}
          <div style={{ minWidth: 0 }}>
            {hasInlineResult ? (
              inlineSummaries.map((summary, idx) => (
                <div key={idx} className="truncate" style={{ color: 'inherit' }}>
                  <span style={{ fontWeight: 500 }}>{displayName}</span>
                  <span style={{ opacity: 0.55, marginLeft: '6px' }}>{summary}</span>
                </div>
              ))
            ) : displayProcess.isInProgress ? (
              <TextShimmer
                as="span"
                className="font-medium text-[13px] [--base-color:var(--Labels-Secondary)] [--base-gradient-color:var(--color-text-primary)]"
                duration={1.5}
              >
                {`${displayName} ${getInProgressText(rawToolName, displayProcess.toolCall) || ''}`}
              </TextShimmer>
            ) : (
              <span style={{ fontWeight: 500 }}>{displayName}</span>
            )}
          </div>
        </Tag>
      </div>
    );
  }

  const handleToggle = () => {
    // For file tools with a valid path and onOpenFile callback, open in file panel
    if (isFileTool && filePath && onOpenFile) {
      onOpenFile(filePath);
      return;
    }
    // If a detail click handler is provided, open in detail panel instead of inline expand
    if (onDetailClick) {
      onDetailClick(displayProcess);
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
        className="transition-colors hover:bg-foreground/10"
        style={{
          boxSizing: 'border-box',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '14px',
          lineHeight: '20px',
          color: isFailed ? 'var(--color-loss)' : 'var(--Labels-Secondary)',
          padding: '4px 12px',
          borderRadius: '6px',
          backgroundColor: displayProcess.isInProgress
            ? 'var(--color-accent-soft)'
            : 'transparent',
          border: displayProcess.isInProgress
            ? '1px solid var(--color-border-muted)'
            : 'none',
          width: '100%',
        }}
        title={displayProcess.isInProgress ? 'Tool call in progress...' : 'View tool call details'}
      >
        {/* Icon */}
        <div className="flex-shrink-0">
          <IconComponent
            className="h-4 w-4"
            style={{ color: displayProcess.isFailed ? 'var(--color-loss)' : 'var(--Labels-Secondary)' }}
          />
        </div>

        {/* Tool name label + in-progress text or summary */}
        {displayProcess.isInProgress ? (
          <TextShimmer
            as="span"
            className="font-medium text-[13px] [--base-color:var(--Labels-Secondary)] [--base-gradient-color:var(--color-text-primary)]"
            duration={1.5}
          >
            {`${displayName} ${getInProgressText(rawToolName, displayProcess.toolCall) || ''}`}
          </TextShimmer>
        ) : (
          <span style={{ color: 'inherit' }}>{displayName}</span>
        )}

        {/* Status indicator */}
        {displayProcess.isComplete && !displayProcess.isInProgress && (
          <span
            className="text-xs"
            style={{
              color: 'inherit',
              opacity: 0.8
            }}
          >
            {(() => {
              const summary = getExpandableSummary(rawToolName, displayProcess);
              return summary || (displayProcess.isFailed ? '(failed)' : '(complete)');
            })()}
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
        <div className="mt-2 space-y-3">
          {processes.map((proc, idx) => {
            if (!proc.toolCallResult) return null;
            const rawContent = typeof proc.toolCallResult.content === 'string'
              ? proc.toolCallResult.content
              : String(proc.toolCallResult.content ?? '');

            // Check for truncated results
            const truncated = parseTruncatedResult(rawContent);
            if (truncated.isTruncated) {
              return (
                <div key={idx} className="text-xs">
                  {processes.length > 1 && (
                    <p className="mb-2" style={{ color: 'var(--color-text-primary)' }}>
                      Result ({idx + 1}/{processes.length}):
                    </p>
                  )}
                  <div
                    className="px-3 py-2 rounded"
                    style={{
                      backgroundColor: 'var(--color-accent-soft)',
                      border: '1px solid var(--color-border-muted)',
                      color: 'var(--color-text-primary)',
                    }}
                  >
                    <div className="flex items-start gap-2">
                      <FileText className="h-4 w-4 flex-shrink-0 mt-0.5" style={{ color: 'var(--color-accent-primary)' }} />
                      <div className="space-y-1.5 min-w-0">
                        <p className="text-xs font-medium" style={{ color: 'var(--color-text-primary)' }}>
                          Result too large to display inline
                        </p>
                        {truncated.filePath && onOpenFile && (
                          <button
                            onClick={() => onOpenFile(truncated.filePath)}
                            className="flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-colors hover:bg-foreground/10"
                            style={{
                              color: 'var(--color-accent-primary)',
                              border: '1px solid var(--color-accent-overlay)',
                            }}
                          >
                            <FileText className="h-3 w-3" />
                            Open full result
                          </button>
                        )}
                        {truncated.filePath && (
                          <p className="text-xs font-mono truncate" style={{ color: 'var(--color-text-tertiary)' }}>
                            {truncated.filePath}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            }

            const isError = rawContent.trim().startsWith('ERROR');
            const formatted = formatExpandedContent(proc.toolName || rawToolName, proc);
            const displayContent = formatted || stripLineNumbers(rawContent) || 'No result content';
            return (
              <div key={idx} className="text-xs">
                {processes.length > 1 && (
                  <p className="mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Result ({idx + 1}/{processes.length}):
                  </p>
                )}
                <Markdown
                  variant="panel"
                  content={displayContent}
                  className="px-3 py-2 rounded text-xs"
                  style={{
                    backgroundColor: isError ? 'var(--color-loss-soft)' : 'var(--color-accent-soft)',
                    border: `1px solid ${isError ? 'var(--color-border-loss)' : 'var(--color-border-muted)'}`,
                  }}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default ToolCallMessageContent;
