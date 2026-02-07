import React from 'react';
import { Bot, CheckCircle2, Circle, Loader2, X } from 'lucide-react';
import { ScrollArea } from '../../../components/ui/scroll-area';
import { cn } from '../../../lib/utils';
import AgentTabBar from './AgentTabBar';
import SubagentCardContent from './SubagentCardContent';
import iconFile from '../../../assets/img/icon-file.svg';
import iconRobo from '../../../assets/img/icon-robo.svg';
import '../components/FilePanel.css';

/**
 * AgentPanel Component
 *
 * Right-side panel that displays the selected agent's details and messages.
 * Features:
 * - Shows agent header with status
 * - Displays agent messages using SubagentCardContent
 * - Bottom tab bar for switching between agents
 *
 * @param {Object} props
 * @param {Array} props.agents - Array of agent objects
 * @param {string} props.selectedAgentId - Currently selected agent ID
 * @param {Function} props.onSelectAgent - Callback when agent is selected (pass null to deselect)
 * @param {Function} props.onClose - Callback to close the entire agent panel
 * @param {Function} props.onRemoveAgent - Callback to remove an agent from the list
 */
function AgentPanel({ agents, selectedAgentId, onSelectAgent, onClose, onRemoveAgent }) {
  // Find the selected agent
  const selectedAgent = agents.find(agent => agent.id === selectedAgentId);

  // Render empty state with card container if no agents
  if (agents.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center relative"
        style={{
          background: 'transparent',
          width: '100%',
          height: '100%',
          borderRadius: '16px',
          padding: '16px',
          boxSizing: 'border-box',
        }}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="file-panel-icon-btn absolute top-4 right-4"
          title="Close"
        >
          <X className="h-4 w-4" />
        </button>

        <img src={iconRobo} alt="No agents" className="h-12 w-12 mb-4" style={{ opacity: 0.3 }} />
        <p className="text-sm" style={{ color: 'rgba(255, 255, 255, 0.5)' }}>
          No agents running
        </p>
      </div>
    );
  }

  // Render empty state with card container if no agent selected
  if (!selectedAgent) {
    return (
      <div
        className="flex flex-col items-center justify-center relative"
        style={{
          background: 'transparent',
          width: '100%',
          height: '100%',
          borderRadius: '16px',
          padding: '16px',
          boxSizing: 'border-box',
        }}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="file-panel-icon-btn absolute top-4 right-4"
          title="Close"
        >
          <X className="h-4 w-4" />
        </button>

        <img src={iconRobo} alt="Select agent" className="h-12 w-12 mb-4" style={{ opacity: 0.3 }} />
        <p className="text-sm" style={{ color: 'rgba(255, 255, 255, 0.5)' }}>
          Select an agent to view details
        </p>
      </div>
    );
  }

  /**
   * Get status icon based on agent status
   */
  const getStatusIcon = () => {
    if (selectedAgent.currentTool) {
      return <Loader2 className="h-4 w-4 animate-spin" style={{ color: 'rgba(255, 255, 255, 0.4)' }} />;
    }
    if (selectedAgent.status === 'active' && selectedAgent.messages.length > 0) {
      return <Loader2 className="h-4 w-4 animate-spin" style={{ color: 'rgba(255, 255, 255, 0.4)' }} />;
    }
    if (selectedAgent.status === 'completed') {
      return <CheckCircle2 className="h-4 w-4" style={{ color: '#0FEDBE' }} />;
    }
    return <Circle className="h-4 w-4" style={{ color: 'rgba(255, 255, 255, 0.3)' }} />;
  };

  /**
   * Get status text
   */
  const getStatusText = () => {
    if (selectedAgent.currentTool) {
      return `Running: ${selectedAgent.currentTool}`;
    }
    if (selectedAgent.status === 'completed') {
      if (selectedAgent.toolCalls > 0) {
        return `Completed (${selectedAgent.toolCalls} tool calls)`;
      }
      return 'Completed';
    }
    if (selectedAgent.status === 'active') {
      if (selectedAgent.messages.length > 0) {
        return 'Running';
      }
      return 'Initializing';
    }
    return 'Initializing';
  };

  return (
    <div
      className="flex flex-col"
      style={{
        background: 'transparent',
        width: '100%',
        height: '100%',
        borderRadius: '16px',
        padding: '0 16px 16px',
        boxSizing: 'border-box',
      }}
    >
      {/* Header - Computer Style */}
      <div className="flex-shrink-0 pt-4">
        <div className="pb-4">
          {/* File Icon + Title + Close Button */}
          <div className="flex items-center gap-3">
            {/* File Icon */}
            <img
              src={iconFile}
              alt="Agent"
              style={{ width: '32px', height: '32px', flexShrink: 0 }}
            />

            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium" style={{ color: '#FFFFFF' }}>
                {selectedAgent.name}
              </div>

              {/* Status Bar */}
              <div className="flex items-center gap-2 mt-1">
                {getStatusIcon()}
                <span
                  className="text-xs"
                  style={{
                    color: selectedAgent.status === 'completed' ? '#0FEDBE' : 'rgba(255, 255, 255, 0.6)'
                  }}
                >
                  {getStatusText()}
                </span>
              </div>
            </div>

            {/* Close Button - Close entire agent panel */}
            <button
              onClick={onClose}
              className="file-panel-icon-btn"
              title="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Current Tool Display */}
          {selectedAgent.currentTool && (
            <div className="mt-3 flex items-center gap-2 text-xs" style={{ color: 'rgba(255, 255, 255, 0.7)' }}>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 1024 1024"
                style={{ color: '#6155F5' }}
              >
                <path
                  d="M516.266667 85.333333c89.429333 0 171.221333 13.738667 231.978666 37.290667 30.293333 11.733333 57.258667 26.624 77.397334 45.141333 20.138667 18.517333 36.224 43.52 36.266666 74.112v354.133334l-0.085333 0.213333 0.042667 0.213333v177.194667c0 30.592-16.085333 55.594667-36.266667 74.112-20.053333 18.474667-47.104 33.408-77.354667 45.141333-60.757333 23.509333-142.506667 37.290667-231.978666 37.290667-89.472 0-171.178667-13.781333-231.978667-37.290667-30.293333-11.733333-57.301333-26.666667-77.397333-45.141333C186.752 829.226667 170.666667 804.266667 170.666667 773.632V241.877333c0-30.592 16.042667-55.594667 36.224-74.112 20.096-18.517333 47.146667-33.408 77.397333-45.141333C345.088 99.114667 426.794667 85.333333 516.266667 85.333333z"
                  fill="currentColor"
                />
              </svg>
              <span>Running: {selectedAgent.currentTool}</span>
            </div>
          )}
        </div>
      </div>

      {/* Content Area - Scrollable */}
      <div className="flex-1 overflow-hidden" style={{ minHeight: 0 }}>
        <ScrollArea className="h-full w-full">
          <div className="pt-4">
            <SubagentCardContent
              taskId={selectedAgent.taskId}
              description={selectedAgent.description}
              type={selectedAgent.type}
              toolCalls={selectedAgent.toolCalls}
              currentTool={selectedAgent.currentTool}
              status={selectedAgent.status}
              messages={selectedAgent.messages}
              isHistory={false}
            />
          </div>
        </ScrollArea>
      </div>

      {/* Bottom Tab Bar */}
      {agents.length > 1 && (
        <div className="flex-shrink-0">
          <AgentTabBar
            agents={agents}
            selectedAgentId={selectedAgentId}
            onSelectAgent={onSelectAgent}
            onRemoveAgent={onRemoveAgent}
          />
        </div>
      )}
    </div>
  );
}

export default AgentPanel;
