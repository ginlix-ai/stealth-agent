import React from 'react';
import { Check, Loader2, ArrowRight, RotateCw, RefreshCw } from 'lucide-react';
import iconRobo from '../../../assets/img/icon-robo.png';
import iconRoboSing from '../../../assets/img/icon-robo-sing.png';
import './AgentSidebar.css';

/**
 * Extract a short one-line summary from a full task description.
 * Takes the first sentence or first line, truncated to maxLen chars.
 */
function summarize(text, maxLen = 100) {
  if (!text || typeof text !== 'string') return '';
  // Take first line only
  const firstLine = text.split(/\n/)[0].trim();
  // Remove trailing colon (often "Research X comprehensively. Cover:")
  const cleaned = firstLine.replace(/:$/, '');
  if (cleaned.length <= maxLen) return cleaned;
  return cleaned.slice(0, maxLen).replace(/\s+\S*$/, '') + '…';
}

const CARD_BORDER = 'rgba(255,255,255,0.06)';

/**
 * SubagentTaskMessageContent Component
 *
 * Renders a compact, clickable card in the main chat view to indicate that
 * a background subagent task was launched or resumed (via the `task` tool).
 * Uses the same visual style as inline artifact cards (company overview, etc.).
 */
function SubagentTaskMessageContent({
  subagentId,
  description,
  type = 'general-purpose',
  status = 'unknown',
  resumed = false, // false | true | 'updated'
  resumeTargetId,
  onOpen,
  onDetailOpen,
  toolCallProcess,
}) {
  if (!subagentId && !description) {
    return null;
  }

  const isRunning = status === 'running';
  const isCompleted = status === 'completed';
  const hasResult = isCompleted && toolCallProcess?.toolCallResult?.content;
  const summary = summarize(description);

  const handleCardClick = () => {
    if (onOpen) {
      // For resume cards, open the original subagent's tab if possible
      onOpen({ subagentId: resumeTargetId || subagentId, description, type, status });
    }
  };

  const handleViewOutput = (e) => {
    e.stopPropagation();
    if (onDetailOpen && toolCallProcess) {
      onDetailOpen(toolCallProcess);
    }
  };

  return (
    <div
      style={{
        background: 'rgba(255,255,255,0.03)',
        border: `1px solid ${CARD_BORDER}`,
        borderRadius: 8,
        padding: '12px 14px',
        cursor: 'pointer',
        transition: 'border-color 0.15s',
      }}
      onClick={handleCardClick}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)')}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = CARD_BORDER)}
      title={resumed === 'updated' ? 'Click to view updated subagent' : resumed ? 'Click to view resumed subagent' : isRunning ? 'Click to view running subagent' : 'Click to view subagent details'}
    >
      {/* Top row: icon + summary text */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <div style={{ position: 'relative', flexShrink: 0 }}>
          <img
            src={isCompleted ? iconRobo : iconRoboSing}
            alt="Subagent"
            className={isRunning ? 'agent-tab-active-pulse' : ''}
            style={{ width: 20, height: 20 }}
          />
          {isRunning && (
            <Loader2
              style={{
                width: 10, height: 10,
                position: 'absolute', bottom: -2, right: -2,
                color: '#6155F5',
                animation: 'spin 1s linear infinite',
              }}
            />
          )}
        </div>
        <span style={{ fontWeight: 600, color: '#fff', fontSize: 14, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {summary || 'Subagent Task'}
        </span>
        {hasResult && (
          <ArrowRight
            style={{ width: 14, height: 14, flexShrink: 0, color: '#6155F5' }}
            onClick={handleViewOutput}
          />
        )}
      </div>

      {/* Bottom row: type badge + status */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)' }}>
          {type}
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: resumed ? '#E8A838' : isRunning ? '#6155F5' : isCompleted ? '#6155F5' : 'rgba(255,255,255,0.4)' }}>
          {resumed === 'updated' && <RefreshCw style={{ width: 12, height: 12 }} />}
          {resumed && resumed !== 'updated' && <RotateCw style={{ width: 12, height: 12 }} />}
          {!resumed && isRunning && <Loader2 style={{ width: 12, height: 12, animation: 'spin 1s linear infinite' }} />}
          {!resumed && isCompleted && <Check style={{ width: 12, height: 12 }} />}
          {resumed === 'updated' ? 'Updated' : resumed ? 'Resumed' : isRunning ? 'Running' : isCompleted ? 'Completed' : status}
        </span>
      </div>
    </div>
  );
}

export default SubagentTaskMessageContent;
