import React, { useState, useRef, useCallback } from 'react';
import { CheckCircle2, Circle, Loader2, MessageSquarePlus, Send, X } from 'lucide-react';
import { cn } from '../../../lib/utils';
import iconRobo from '../../../assets/img/icon-robo.png';
import iconRoboSing from '../../../assets/img/icon-robo-sing.png';
import Markdown from './Markdown';
import { sendSubagentMessage } from '../utils/api';
import './AgentSidebar.css';

/**
 * SubagentStatusBar Component
 *
 * Replaces the chat input area when viewing a subagent tab.
 * Shows agent avatar, name, description, status, and current tool.
 * Includes an expandable input for sending instructions to running subagents.
 *
 * @param {Object} agent - The agent object from the agents array
 * @param {string} threadId - The current thread ID
 */
function SubagentStatusBar({ agent, threadId, onInstructionSent }) {
  const [inputOpen, setInputOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [sending, setSending] = useState(false);
  const inputRef = useRef(null);

  if (!agent) return null;

  const messages = agent.messages || [];

  // Derive streaming state from messages (self-sufficient, no subagent_status dependency)
  const lastAssistant = [...messages].reverse().find(m => m.role === 'assistant');
  const isMessageStreaming = lastAssistant?.isStreaming === true;

  // Derive current tool from message state
  const derivedCurrentTool = (() => {
    if (agent.currentTool) return agent.currentTool;
    if (!lastAssistant?.toolCallProcesses) return '';
    const inProgress = Object.values(lastAssistant.toolCallProcesses).find(p => p.isInProgress);
    return inProgress?.toolName || '';
  })();

  // Effective status: prefer message-derived state, fall back to card status
  const effectiveStatus = messages.length === 0
    ? 'initializing'
    : isMessageStreaming || derivedCurrentTool
      ? 'active'
      : (lastAssistant && lastAssistant.isStreaming === false) ? 'completed' : agent.status;

  const isActive = effectiveStatus === 'active';
  const isCompleted = effectiveStatus === 'completed';

  // Extract task ID from display ID (e.g. "Task-k7Xm2p" → "k7Xm2p")
  const taskId = agent.name?.replace('Task-', '') || null;

  // Can send: subagent is still running, we have a thread and task ID
  const canSend = !isCompleted && threadId && taskId != null;

  const getStatusIcon = () => {
    if (derivedCurrentTool) {
      return <Loader2 className="h-4 w-4 animate-spin" style={{ color: 'rgba(255, 255, 255, 0.4)' }} />;
    }
    if (isActive) {
      return <Loader2 className="h-4 w-4 animate-spin" style={{ color: 'rgba(255, 255, 255, 0.4)' }} />;
    }
    if (isCompleted) {
      return <CheckCircle2 className="h-4 w-4" style={{ color: '#6155F5' }} />;
    }
    return <Circle className="h-4 w-4" style={{ color: 'rgba(255, 255, 255, 0.3)' }} />;
  };

  const getStatusText = () => {
    if (derivedCurrentTool) {
      return `Running: ${derivedCurrentTool}`;
    }
    if (isCompleted) {
      if (agent.toolCalls > 0) {
        return `Completed (${agent.toolCalls} tool calls)`;
      }
      return 'Completed';
    }
    if (isActive) {
      return 'Running';
    }
    return 'Initializing';
  };

  const handleSend = useCallback(async () => {
    const text = inputValue.trim();
    if (!text || !canSend || sending) return;

    // Immediately show pending message in the subagent view
    onInstructionSent?.(text);

    setSending(true);
    setInputValue('');
    setInputOpen(false);
    try {
      await sendSubagentMessage(threadId, taskId, text);
    } catch (err) {
      console.error('[SubagentStatusBar] Failed to send message:', err);
    } finally {
      setSending(false);
    }
  }, [inputValue, canSend, sending, threadId, taskId, onInstructionSent]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
    if (e.key === 'Escape') {
      setInputOpen(false);
      setInputValue('');
    }
  }, [handleSend]);

  return (
    <div className="space-y-2">
      <div
        className="flex items-center gap-3 px-4 py-3 rounded-lg"
        style={{
          backgroundColor: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
        }}
      >
        {/* Agent avatar */}
        <div
          className={cn(
            "w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0",
            isActive && !isCompleted && "agent-tab-active-pulse"
          )}
          style={{
            backgroundColor: isActive && !isCompleted
              ? 'rgba(97, 85, 245, 0.25)'
              : 'rgba(255, 255, 255, 0.1)',
          }}
        >
          <img
            src={isCompleted ? iconRobo : iconRoboSing}
            alt="Agent"
            className="h-5 w-5"
            style={{ filter: 'brightness(0) saturate(100%) invert(100%)' }}
          />
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-white truncate">
              {agent.name}
            </span>
            <span
              className="text-xs px-1.5 py-0.5 rounded"
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.06)',
                color: 'rgba(255, 255, 255, 0.5)',
              }}
            >
              {agent.type}
            </span>
          </div>
          {agent.description && (
            <div
              className="mt-0.5"
              style={{
                color: 'rgba(255, 255, 255, 0.5)',
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
              }}
            >
              <Markdown variant="compact" content={agent.description} className="text-xs" />
            </div>
          )}
        </div>

        {/* Right side: status + instruction button stacked */}
        <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
          <div className="flex items-center gap-1.5">
            {getStatusIcon()}
            <span className="text-xs whitespace-nowrap" style={{ color: isCompleted ? '#6155F5' : 'rgba(255, 255, 255, 0.5)' }}>
              {getStatusText()}
            </span>
          </div>
          {canSend && !inputOpen && (
            <button
              onClick={() => {
                setInputOpen(true);
                setTimeout(() => inputRef.current?.focus(), 50);
              }}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs transition-colors"
              style={{
                backgroundColor: 'rgba(97, 85, 245, 0.15)',
                color: 'rgba(255, 255, 255, 0.7)',
                border: '1px solid rgba(97, 85, 245, 0.25)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(97, 85, 245, 0.25)';
                e.currentTarget.style.color = 'rgba(255, 255, 255, 0.9)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(97, 85, 245, 0.15)';
                e.currentTarget.style.color = 'rgba(255, 255, 255, 0.7)';
              }}
            >
              <MessageSquarePlus className="h-3.5 w-3.5" />
              <span>Instruct</span>
            </button>
          )}
        </div>
      </div>

      {/* Expandable instruction input */}
      {inputOpen && (
        <div
          className="flex items-center gap-2 px-3 py-2 rounded-lg"
          style={{
            backgroundColor: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid rgba(97, 85, 245, 0.3)',
          }}
        >
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Add instruction for this agent..."
            disabled={sending}
            className="flex-1 bg-transparent text-sm text-white placeholder-white/30 outline-none"
          />
          <div className="flex items-center gap-1">
            <button
              onClick={() => { setInputOpen(false); setInputValue(''); }}
              disabled={sending}
              className="p-1 rounded transition-colors"
              style={{ color: 'rgba(255, 255, 255, 0.4)' }}
              onMouseEnter={(e) => { e.currentTarget.style.color = 'rgba(255, 255, 255, 0.7)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'rgba(255, 255, 255, 0.4)'; }}
            >
              <X className="h-4 w-4" />
            </button>
            <button
              onClick={handleSend}
              disabled={!inputValue.trim() || sending}
              className="p-1 rounded transition-colors"
              style={{
                color: inputValue.trim() && !sending ? '#6155F5' : 'rgba(255, 255, 255, 0.2)',
              }}
              onMouseEnter={(e) => {
                if (inputValue.trim() && !sending) e.currentTarget.style.color = '#7B6FFF';
              }}
              onMouseLeave={(e) => {
                if (inputValue.trim() && !sending) e.currentTarget.style.color = '#6155F5';
              }}
            >
              {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default SubagentStatusBar;
